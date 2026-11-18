"""Known-schema and adversarial coverage contracts, no native dependency."""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/common/tools"))
import lsp_index_coverage
from lsp_index_cache import Cache
from lsp_index_coverage import certify, decode_metadata, source_identity, uri_identity
from lsp_index_policy import STRINGS_BYTES, IndexUnavailable
from lsp_index_resources import Deadline


def varint(n):
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def riff(chunks):
    body = b'CdIx' + b''.join(tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'') for tag, data in chunks)
    return b'RIFF' + struct.pack('<I', len(body)) + body


def shard(path, *, flags=1, version=20, source_uri=None, command_path=None):
    # Independent minimal RIFF fixture: one TU, empty symbol/ref slabs and
    # explicit compile-source metadata. Body semantics are native's concern.
    strings = ['', source_uri or path.as_uri(), str(path.parent), '/usr/bin/clang', str(command_path or path)]
    table = ('\0'.join(strings) + '\0').encode()
    return riff([(b'meta', struct.pack('<I', version)), (b'stri', struct.pack('<I', len(table)) + zlib.compress(table)),
                 (b'srcs', bytes([flags]) + varint(1) + b'abcdefgh' + varint(0)),
                 (b'cmdl', varint(2) + varint(2) + varint(3) + varint(4)),
                 (b'symb', b''), (b'refs', b'')])


def chunks_from(raw):
    body = raw[12:]
    chunks, pos = [], 0
    while pos < len(body):
        tag, size = body[pos:pos + 4], struct.unpack_from('<I', body, pos + 4)[0]
        pos += 8
        data = body[pos:pos + size]
        pos += size + (size & 1)
        chunks.append((tag, data))
    return chunks


class CoverageContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.workspace = self.base / 'work'
        self.plugin = self.base / 'plugin'
        self.workspace.mkdir()
        self.plugin.mkdir()
        self.one = self.workspace / 'one/same.c'
        self.two = self.workspace / 'two/same.c'
        for f in [self.one, self.two]:
            f.parent.mkdir()
            f.write_text('int target;\n')
        self.cache = Cache(self.base / 'cache', self.workspace, self.plugin)
        self.addCleanup(self.cache.close)

    def sources(self):
        return [source_identity(self.one), source_identity(self.two)]

    def files(self, lease):
        folder = lease.path / '.cache/clangd/index'
        folder.mkdir(parents=True)
        first = folder / ('same.c.' + 'A' * 16 + '.idx')
        second = folder / ('same.c.' + 'B' * 16 + '.idx')
        first.write_bytes(shard(self.one))
        second.write_bytes(shard(self.two))
        return first, second

    def test_same_basename_tus_need_independent_exact_uri_metadata(self):
        with self.cache.lease('a' * 64, Deadline(5)) as lease:
            self.files(lease)
            result = certify(lease.fd, self.sources(), lease.deadline, validate_anchor=lease.validate)
            self.assertTrue(result.complete)
            self.assertEqual((result.total, result.covered), (2, 2))

    def test_skip_or_only_one_of_same_basename_does_not_cover_both(self):
        with self.cache.lease('b' * 64, Deadline(5)) as lease:
            _, second = self.files(lease)
            second.unlink()
            result = certify(lease.fd, self.sources(), lease.deadline)
            self.assertFalse(result.complete)
            self.assertEqual((result.covered, result.reason), (1, 'index_coverage_unverified'))

    def test_had_errors_remains_partial_even_when_all_tus_have_shards(self):
        with self.cache.lease('c' * 64, Deadline(5)) as lease:
            first, _ = self.files(lease)
            first.write_bytes(shard(self.one, flags=3))
            result = certify(lease.fd, self.sources(), lease.deadline)
            self.assertEqual((result.complete, result.covered, result.reason), (False, 2, 'index_had_errors'))

    def test_header_cannot_impersonate_tu_and_command_must_match(self):
        for raw in [shard(self.one, flags=0), shard(self.one, command_path=self.two), shard(self.one, flags=5)]:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                decode_metadata(raw, Deadline(5))

    def test_foreign_tu_and_duplicate_mapping_are_not_coverage(self):
        with self.cache.lease('d' * 64, Deadline(5)) as lease:
            first, second = self.files(lease)
            second.write_bytes(shard(self.one))
            self.assertFalse(certify(lease.fd, self.sources(), lease.deadline).complete)
            foreign = self.base / 'same.c'
            foreign.write_text('int foreign;\n')
            first.write_bytes(shard(foreign))
            self.assertFalse(certify(lease.fd, self.sources(), lease.deadline).complete)

    def test_empty_or_duplicate_compilation_scope_not_silently_reduced(self):
        with self.cache.lease('e' * 64, Deadline(5)) as lease:
            for sources in [[], [source_identity(self.one)] * 2]:
                with self.subTest(sources=sources), self.assertRaises(IndexUnavailable) as e:
                    certify(lease.fd, sources, lease.deadline)
                self.assertEqual(e.exception.reason, 'compile_db_unsupported')

    def test_corrupt_unknown_and_missing_chunks_do_not_throw_from_certify(self):
        valid = shard(self.one)
        values = [b'', valid[:-1], b'BAD!' + valid[4:], shard(self.one, version=999),
                  valid[:16] + struct.pack('<I', 0xffffffff) + valid[20:], riff([(b'meta', struct.pack('<I', 20))])]
        with self.cache.lease('f' * 64, Deadline(5)) as lease:
            first, _ = self.files(lease)
            for raw in values:
                with self.subTest(raw=raw[:24]):
                    first.write_bytes(raw)
                    result = certify(lease.fd, self.sources(), lease.deadline)
                    self.assertFalse(result.complete)
                    self.assertEqual(result.reason, 'index_coverage_unverified')

    def test_zlib_bomb_and_unknown_schema_safely_degrade(self):
        bomb = zlib.compress(b'x' * (STRINGS_BYTES * 2))
        raw = riff([(b'meta', struct.pack('<I', 20)),
                    (b'stri', struct.pack('<I', STRINGS_BYTES) + bomb),
                    (b'srcs', b''), (b'cmdl', b''), (b'symb', b''), (b'refs', b'')])
        real_factory = zlib.decompressobj
        observed = []

        class Probe:
            def __init__(self, wrapped):
                self.wrapped = wrapped
            def decompress(self, data, max_length=0):
                observed.append(max_length)
                return (self.wrapped.decompress(data, max_length) if max_length
                        else self.wrapped.decompress(data))
            def __getattr__(self, name):
                return getattr(self.wrapped, name)

        with (patch.object(lsp_index_coverage.zlib, 'decompressobj',
                           side_effect=lambda: Probe(real_factory())),
              self.assertRaises(ValueError)):
            decode_metadata(raw, Deadline(5))
        self.assertEqual(observed, [STRINGS_BYTES + 1])
        with self.assertRaises(ValueError):
            decode_metadata(shard(self.one, version=21), Deadline(5))

    def test_duplicate_chunk_rejected(self):
        chunks = chunks_from(shard(self.one))
        with self.assertRaises(ValueError):
            decode_metadata(riff([*chunks, chunks[0]]), Deadline(5))

    def test_unknown_chunk_tag_rejected(self):
        chunks = chunks_from(shard(self.one))
        raw = riff([(b'NOPE', chunks[0][1]), *chunks[1:]])
        with self.assertRaises(ValueError):
            decode_metadata(raw, Deadline(5))

    def test_unused_compressed_data_rejected(self):
        chunks = chunks_from(shard(self.one))
        string_chunk = chunks[1][1]
        count = struct.unpack_from('<I', string_chunk)[0]
        raw = riff([*chunks[:1], (b'stri', struct.pack('<I', count) + string_chunk[4:] + b'junk'),
                    *chunks[2:]])
        with self.assertRaises(ValueError):
            decode_metadata(raw, Deadline(5))

    def test_nonzero_odd_chunk_padding_rejected(self):
        chunks = chunks_from(shard(self.one))
        raw = bytearray(shard(self.one))
        offset = 12
        for _tag, data in chunks:
            if len(data) % 2:
                raw[offset + 8 + len(data)] = 1
                break
            offset += 8 + len(data)
        with self.assertRaises(ValueError):
            decode_metadata(bytes(raw), Deadline(5))

    def test_five_byte_varint_overflow_rejected(self):
        with self.assertRaises(ValueError):
            lsp_index_coverage.Reader(b'\x80\x80\x80\x80\x10').varint()
        chunks = chunks_from(shard(self.one))
        bad_varint = b'\x01' + b'\x80\x80\x80\x80\x10' + b'abcdefgh\0'
        raw = riff([*chunks[:2], (b'srcs', bad_varint), *chunks[3:]])
        with self.assertRaises(ValueError):
            decode_metadata(raw, Deadline(5))

    def test_string_index_out_of_range_rejected(self):
        chunks = chunks_from(shard(self.one))
        bad_index = b'\x01' + varint(999) + b'abcdefgh\0'
        raw = riff([*chunks[:2], (b'srcs', bad_index), *chunks[3:]])
        with self.assertRaises(ValueError):
            decode_metadata(raw, Deadline(5))

    def test_golden_apple_clangd_shard_v20(self):
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/lsp-index/apple-clangd21-cdix20-main.idx'
        raw = fixture.read_bytes()
        golden_path = self.workspace / 'main.c'
        golden_path.write_text('int golden;\n')
        authored = source_identity(golden_path)
        with patch.object(lsp_index_coverage, 'source_identity', return_value=authored):
            source, errors = decode_metadata(raw, Deadline(5))
        self.assertEqual(source.identity, authored.identity)
        self.assertFalse(errors)

    def test_golden_shard_contains_no_maintainer_home_path(self):
        fixture = Path(__file__).resolve().parents[1] / 'fixtures/lsp-index/apple-clangd21-cdix20-main.idx'
        string_chunk = next(data for tag, data in chunks_from(fixture.read_bytes()) if tag == b'stri')
        text = zlib.decompress(string_chunk[4:])
        self.assertNotIn(b'/Users/', text)
        self.assertNotIn(b'/home/', text)

    def test_fifo_candidate_is_rejected_without_blocking(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO is unavailable on this platform')
        with self.cache.lease('9' * 64, Deadline(5)) as lease:
            folder = lease.path / '.cache/clangd/index'
            folder.mkdir(parents=True)
            os.mkfifo(folder / ('same.c.' + 'C' * 16 + '.idx'))
            result = certify(lease.fd, self.sources(), lease.deadline)
            self.assertFalse(result.complete)
            self.assertEqual(result.reason, 'index_coverage_unverified')

    def test_intermediate_or_leaf_symlink_not_followed(self):
        with self.cache.lease('1' * 64, Deadline(5)) as lease:
            first, _ = self.files(lease)
            original = first.read_bytes()
            first.unlink()
            foreign = self.base / 'foreign.idx'
            foreign.write_bytes(original)
            first.symlink_to(foreign)
            self.assertFalse(certify(lease.fd, self.sources(), lease.deadline).complete)
            first.unlink()
            first.write_bytes(original)
            folder = first.parent
            folder.rename(folder.with_name('saved'))
            folder.symlink_to(folder.with_name('saved'), target_is_directory=True)
            self.assertFalse(certify(lease.fd, self.sources(), lease.deadline).complete)
            self.assertEqual(foreign.read_bytes(), original)
            folder.unlink()
            folder.with_name('saved').rename(folder)

    def test_coverage_refuses_non_private_key_directory(self):
        with self.cache.lease('2' * 64, Deadline(5)) as lease:
            self.files(lease)
            lease.path.chmod(0o755)
            try:
                result = certify(lease.fd, self.sources(), lease.deadline)
            finally:
                lease.path.chmod(0o700)
            self.assertEqual((result.complete, result.reason), (False, 'index_coverage_unverified'))

    def test_symlink_loop_in_shard_metadata_degrades_to_fixed_partial(self):
        loop_a = self.workspace / 'loop-a.c'
        loop_b = self.workspace / 'loop-b.c'
        loop_a.symlink_to(loop_b)
        loop_b.symlink_to(loop_a)
        with self.cache.lease('4' * 64, Deadline(5)) as lease:
            folder = lease.path / '.cache/clangd/index'
            folder.mkdir(parents=True)
            candidate = folder / ('same.c.' + 'D' * 16 + '.idx')
            candidate.write_bytes(shard(self.one, source_uri=loop_a.as_uri(), command_path=loop_a))
            result = certify(lease.fd, self.sources(), lease.deadline)
            self.assertFalse(result.complete)
            self.assertEqual(result.reason, 'index_coverage_unverified')

    def test_runtime_path_resolution_failure_degrades_to_fixed_partial(self):
        with self.cache.lease('5' * 64, Deadline(5)) as lease:
            folder = lease.path / '.cache/clangd/index'
            folder.mkdir(parents=True)
            candidate = folder / ('same.c.' + 'E' * 16 + '.idx')
            candidate.write_bytes(shard(self.one))
            sources = self.sources()
            with patch.object(lsp_index_coverage, 'source_identity', side_effect=RuntimeError('symlink loop')):
                result = certify(lease.fd, sources, lease.deadline)
            self.assertFalse(result.complete)
            self.assertEqual(result.reason, 'index_coverage_unverified')

    def test_uri_decoding_rejects_remote_and_invalid_percent(self):
        special = self.workspace / 'name space.c'
        special.write_text('int target;\n')
        self.assertEqual(uri_identity(special.as_uri()).identity, source_identity(special).identity)
        for uri in ['https://example.test/main.c', 'file://remote/x', 'file:///x%ZZ', 'file:///x%00', 'file:///x?q=1']:
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                uri_identity(uri)

    def test_filesystem_case_alias_uses_same_identity_when_available(self):
        alternate = str(self.one).replace('/one/', '/ONE/')
        if not Path(alternate).exists():
            # Mandatory Linux contrast: case-distinct regular files are different.
            other = self.workspace / 'ONE/same.c'
            other.parent.mkdir()
            other.write_text('int other;\n')
            self.assertNotEqual(source_identity(other).identity, source_identity(self.one).identity)
        else:
            self.assertEqual(uri_identity(Path(alternate).as_uri()).identity, source_identity(self.one).identity)
            parsed, errors = decode_metadata(shard(self.one, source_uri=Path(alternate).as_uri()), Deadline(5))
            self.assertEqual(parsed.identity, source_identity(self.one).identity)
            self.assertFalse(errors)

    def test_expired_deadline_is_preserved_instead_of_claiming_coverage(self):
        with self.cache.lease('2' * 64, Deadline(5)) as lease:
            self.files(lease)
            now = [0.0]
            d = Deadline(5, clock=lambda: now[0])
            now[0] = 4.0
            with self.assertRaises(IndexUnavailable) as e:
                certify(lease.fd, self.sources(), d)
            self.assertEqual(e.exception.reason, 'index_deadline')


if __name__ == '__main__':
    unittest.main()
