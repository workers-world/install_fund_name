#!/usr/bin/env node
/**
 * GHCR 已发布镜像 → docker save（gzip）→ R2（对齐 ww / framework_sdk_cli 的 package sync 模式）。
 *
 * 前置：宿主机已 docker login ghcr.io；本脚本会 pull、save、上传。
 *
 * Env:
 *   IMAGE              如 ghcr.io/workers-world/install_fund_name
 *   GIT_SHA            完整 commit SHA（用于 :sha-<sha> 与对象键）
 *   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
 *   R2_KEY_PREFIX      可选（WW_ARTIFACTS_R2_KEY_PREFIX）
 */
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { createReadStream, createWriteStream, readFileSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pipeline } from 'node:stream/promises';

const CONTAINER_SUBPATH = 'containers/install_fund_name';
const ARTIFACT_STEM = 'install_fund_name';

function req(name) {
    const v = process.env[name]?.trim();
    if (!v) {
        console.error(`::error::missing env ${name}`);
        process.exit(1);
    }
    return v;
}

function objectPrefix(keyPrefix) {
    const base = CONTAINER_SUBPATH.replace(/^\/+|\/+$/g, '');
    if (!keyPrefix) {
        return base;
    }
    return `${keyPrefix.replace(/\/+$/, '')}/${base}`;
}

function run(cmd, args, opts = {}) {
    const r = spawnSync(cmd, args, { encoding: 'utf8', stdio: ['inherit', 'pipe', 'pipe'], ...opts });
    if (r.status !== 0) {
        const detail = (r.stderr || r.stdout || '').trim();
        console.error(`::error::${cmd} ${args.join(' ')} failed${detail ? `: ${detail}` : ''}`);
        process.exit(1);
    }
    return r.stdout?.trim() ?? '';
}

async function dockerPull(ref) {
    console.log(`Pulling ${ref}`);
    run('docker', ['pull', ref]);
}

function repoDigest(ref) {
    const out = run('docker', ['inspect', '--format', '{{index .RepoDigests 0}}', ref]);
    return out || undefined;
}

async function dockerSaveGzip(ref, destGz) {
    console.log(`Saving ${ref} → ${destGz}`);
    const save = spawnSync('docker', ['save', ref], { stdio: ['inherit', 'pipe', 'pipe'] });
    if (save.status !== 0) {
        console.error(`::error::docker save failed: ${(save.stderr || save.stdout || '').toString().trim()}`);
        process.exit(1);
    }
    const gzip = spawnSync('gzip', ['-c'], {
        input: save.stdout,
        stdio: ['pipe', 'pipe', 'pipe'],
    });
    if (gzip.status !== 0) {
        console.error(`::error::gzip failed: ${(gzip.stderr || gzip.stdout || '').toString().trim()}`);
        process.exit(1);
    }
    const { writeFileSync } = await import('node:fs');
    writeFileSync(destGz, gzip.stdout);
}

function sha256File(path) {
    return new Promise((resolve, reject) => {
        const hash = createHash('sha256');
        const stream = createReadStream(path);
        stream.on('data', (chunk) => hash.update(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(hash.digest('hex')));
    });
}

async function loadS3Client() {
    try {
        return await import('@aws-sdk/client-s3');
    } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        console.error(
            `::error::cannot load @aws-sdk/client-s3 (${detail}). ` +
                'Install beside this script first: npm install --prefix .github/scripts ' +
                '(see .github/scripts/package.json).',
        );
        process.exit(1);
    }
}

async function putObject(client, PutObjectCommand, bucket, key, body, contentType) {
    await client.send(
        new PutObjectCommand({
            Bucket: bucket,
            Key: key,
            Body: body,
            ContentType: contentType,
        }),
    );
    console.log(`Uploaded s3://${bucket}/${key} (${body.length} bytes)`);
}

async function main() {
    const image = req('IMAGE');
    const gitSha = req('GIT_SHA');
    const accountId = req('R2_ACCOUNT_ID');
    const accessKey = req('R2_ACCESS_KEY_ID');
    const secretKey = req('R2_SECRET_ACCESS_KEY');
    const bucket = req('R2_BUCKET');
    const keyPrefix = process.env.R2_KEY_PREFIX?.trim() ?? '';

    const prefix = objectPrefix(keyPrefix);
    const latestRef = `${image}:latest`;
    const shaRef = `${image}:sha-${gitSha}`;

    await dockerPull(latestRef);
    await dockerPull(shaRef);

    const digest = repoDigest(latestRef);
    const tgzPath = join(tmpdir(), `${ARTIFACT_STEM}-${gitSha}-${process.pid}.tar.gz`);
    await dockerSaveGzip(latestRef, tgzPath);
    const checksum = await sha256File(tgzPath);
    const body = readFileSync(tgzPath);

    const { S3Client, PutObjectCommand, GetObjectCommand } = await loadS3Client();
    const client = new S3Client({
        region: 'auto',
        endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
        credentials: { accessKeyId: accessKey, secretAccessKey: secretKey },
    });

    const artifactNames = [
        `${ARTIFACT_STEM}-latest.tar.gz`,
        `${ARTIFACT_STEM}-sha-${gitSha}.tar.gz`,
    ];
    const checksumText = `${checksum}  ${artifactNames[0]}\n`;

    for (const name of artifactNames) {
        const key = `${prefix}/${name}`;
        await putObject(client, PutObjectCommand, bucket, key, body, 'application/gzip');
        const checksumKey = `${key}.sha256`;
        await putObject(
            client,
            PutObjectCommand,
            bucket,
            checksumKey,
            Buffer.from(checksumText, 'utf8'),
            'text/plain; charset=utf-8',
        );
    }

    const manifestKey = `${prefix}/manifest.json`;
    /** @type {Record<string, unknown>} */
    let manifest = { containers: {} };
    try {
        const got = await client.send(new GetObjectCommand({ Bucket: bucket, Key: manifestKey }));
        const text = await got.Body?.transformToString();
        if (text) {
            manifest = JSON.parse(text);
            if (!manifest.containers || typeof manifest.containers !== 'object') {
                manifest.containers = {};
            }
        }
    } catch {
        /* new manifest */
    }

    manifest.containers[ARTIFACT_STEM] = {
        image,
        gitSha,
        tags: ['latest', `sha-${gitSha}`],
        digest: digest ?? null,
        platform: 'linux/amd64',
        platformNote:
            'Single-arch linux/amd64 from GHCR; Apple Silicon Docker Desktop runs it via amd64 emulation.',
        artifacts: artifactNames.map((name) => `${prefix}/${name}`),
        sha256: checksum,
        updatedAt: new Date().toISOString(),
    };
    manifest.updatedAt = new Date().toISOString();

    await putObject(
        client,
        PutObjectCommand,
        bucket,
        manifestKey,
        Buffer.from(JSON.stringify(manifest, null, 2), 'utf8'),
        'application/json',
    );
    console.log(`Updated manifest ${manifestKey}`);

    try {
        unlinkSync(tgzPath);
    } catch {
        /* ignore */
    }
}

main().catch((e) => {
    console.error(`::error::${e instanceof Error ? e.message : String(e)}`);
    process.exit(1);
});
