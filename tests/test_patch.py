"""Patch invariants, without a client installation or StormLib."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('torch_patch', Path(__file__).parents[1] / 'tools/build_patch.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def tiny_model():
    """A 3.3.5 model header with one point light whose tracks have one key each."""
    light = 0x200
    data = bytearray(light + b.M2_LIGHT_SIZE + 0x100)
    struct.pack_into("<4sI", data, 0, b"MD20", 264)
    struct.pack_into("<II", data, b.M2_LIGHTS, 1, light)
    struct.pack_into("<H", data, light, b.POINT_LIGHT)
    at = light + b.M2_LIGHT_SIZE
    for track, size in ((b.DIFFUSE_COLOUR, 12), (b.DIFFUSE_INTENSITY, 4),
                        (b.ATTENUATION_START, 4), (b.ATTENUATION_END, 4)):
        struct.pack_into("<II", data, light + track + 12, 1, at)  # one animation...
        struct.pack_into("<II", data, at, 1, at + 8)              # ...with one key
        at += 8 + size
    return bytes(data)


class MouthPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {}
        spell = [0] * 234
        spell[0], spell[b.F_VISUAL] = b.TEMPLATE_SPELL, 10
        visual = [10, 0, 0, 0, 20]
        kit = [0] * 38
        kit[0], kit[b.K_RIGHT_WEAPON] = 20, b.TEMPLATE_EFFECT_NAME
        # An unrelated attachment must survive every build.
        self.unrelated = [7, 20, 3032, 1, 0, 0, 0, 0, 0, 0]
        for name, rows, fields in [
            ('Spell', [spell], 234), ('SpellVisual', [visual], 5),
            ('SpellVisualKit', [kit], 38),
            ('SpellVisualEffectName', [[3032, 0, 0, 0, 0, 0]], 6),
            ('SpellVisualKitModelAttach', [self.unrelated], 10),
            ('Item', [[1] + [0] * 7], 8),
        ]:
            path = self.root / (name + '.dbc')
            b.write_dbc(path, rows, bytearray(b'\0'), fields)
            self.files['DBFilesClient\\' + name + '.dbc'] = str(path)
        for name, data in ((b.MODEL, tiny_model()), (b.SKIN, b'existing asset')):
            path = self.root / name.split('\\')[-1]
            path.write_bytes(data)
            self.files[name] = str(path)
        self.args = SimpleNamespace(patch_w='fixture', reuse_torch_model=True)

    def patch(self):
        return b.patch_w(self.files, self.args, str(self.root))

    def rows(self, table):
        return b.read_dbc(self.files['DBFilesClient\\' + table + '.dbc'])[0]

    def test_mouth_visual_and_rebuild_are_stable(self):
        self.patch()
        spells = {r[0]: r for r in self.rows('Spell')}
        hand, mouth = spells[90400], spells[90401]
        self.assertEqual([i for i in range(234) if hand[i] != mouth[i]], [0, b.F_VISUAL])
        self.assertEqual(mouth[b.F_AURA_INTERRUPT], 0x80)
        attachments = {r[0]: r for r in self.rows('SpellVisualKitModelAttach')}
        self.assertEqual(attachments[7], self.unrelated)
        self.assertEqual(attachments[90401][1:4], [90401, 90400, 17])
        self.assertNotEqual(attachments[90401][7], 0)  # yaw; pitch/roll stay zero
        self.assertEqual(attachments[90401][8:], [0, 0])
        before = {n: Path(p).read_bytes() for n, p in self.files.items()}
        self.patch()
        self.assertEqual(before, {n: Path(p).read_bytes() for n, p in self.files.items()})

    def test_reused_model_gets_the_hue_safe_light(self):
        self.patch()
        data = Path(self.files[b.MODEL]).read_bytes()
        light = struct.unpack_from('<I', data, b.M2_LIGHTS + 4)[0]

        def key(track, fmt):
            return struct.unpack_from(fmt, data, b.track_keys(data, light + track, 4)[0])

        self.assertEqual(key(b.DIFFUSE_INTENSITY, '<f'), (1.0,))
        self.assertEqual(key(b.ATTENUATION_START, '<f'), (15.0,))
        self.assertEqual(key(b.ATTENUATION_END, '<f'), (22.0,))
        self.assertEqual(key(b.DIFFUSE_COLOUR, '<3f'), struct.unpack('<3f', struct.pack('<3f', 1.0, 0.55, 0.18)))
        self.assertEqual(Path(self.files[b.SKIN]).read_bytes(), b'existing asset')

    def test_occupied_attachment_id_is_rejected(self):
        path = self.files['DBFilesClient\\SpellVisualKitModelAttach.dbc']
        b.write_dbc(path, [[90401, 42, 3032, 1, 0, 0, 0, 0, 0, 0]], bytearray(b'\0'), 10)
        with self.assertRaisesRegex(SystemExit, 'taken by something else'):
            self.patch()

    def test_missing_existing_model_is_rejected(self):
        del self.files[b.MODEL]
        with self.assertRaisesRegex(SystemExit, 'existing ForeverTorch'):
            self.patch()


if __name__ == '__main__':
    unittest.main()
