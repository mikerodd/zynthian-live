import base64
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))

import track_renderer


class ImageRenderingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.track_dir = self.root / 'tracks'
        self.image_dir = self.track_dir / 'imgs'
        self.image_dir.mkdir(parents=True)
        self.track_path = self.track_dir / 'track.json'
        self.track_path.write_text('{}', encoding='utf-8')

    def test_embeds_track_relative_svg(self):
        image_data = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        (self.image_dir / 'riff1.svg').write_bytes(image_data)

        html = track_renderer.build_images_html(
            {'images': ['imgs/riff1.svg']}, str(self.track_path))

        encoded = base64.b64encode(image_data).decode('ascii')
        self.assertIn('class="track-images"', html)
        self.assertIn('src="data:image/svg+xml;base64,{}"'.format(encoded), html)
        self.assertIn('alt="riff1.svg"', html)

    def test_renders_caption_left_of_each_image(self):
        first_data = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
        second_data = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1"/></svg>'
        (self.image_dir / 'first.svg').write_bytes(first_data)
        (self.image_dir / 'second.svg').write_bytes(second_data)

        html = track_renderer.build_images_html(
            {'images': [
                {'caption': 'Riff & 1', 'source': 'imgs/first.svg'},
                {'caption': 'riff2', 'source': 'imgs/second.svg'},
            ]},
            str(self.track_path))

        self.assertEqual(2, html.count('class="track-image"'))
        self.assertIn(
            '<div class="track-image-caption">Riff &amp; 1</div><img',
            html)
        self.assertIn(
            '<div class="track-image-caption">riff2</div><img',
            html)
        self.assertLess(html.index('Riff &amp; 1'), html.index('riff2'))

    def test_preserves_image_order_and_escapes_alt_text(self):
        first_data = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
        second_data = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1"/></svg>'
        (self.image_dir / 'first.svg').write_bytes(first_data)
        (self.image_dir / 'second&riff.svg').write_bytes(second_data)

        html = track_renderer.build_images_html(
            {'images': ['imgs/second&riff.svg', 'imgs/first.svg']},
            str(self.track_path))

        second_encoded = base64.b64encode(second_data).decode('ascii')
        first_encoded = base64.b64encode(first_data).decode('ascii')
        self.assertLess(html.index(second_encoded), html.index(first_encoded))
        self.assertIn('alt="second&amp;riff.svg"', html)

    def test_skips_missing_unsafe_and_unsupported_images(self):
        outside_image = self.root / 'outside.svg'
        outside_image.write_text('<svg/>', encoding='utf-8')
        (self.image_dir / 'notes.txt').write_text('not an image', encoding='utf-8')
        try:
            (self.image_dir / 'escape.svg').symlink_to(outside_image)
            symlink_entry = 'imgs/escape.svg'
        except OSError:
            symlink_entry = None

        entries = [
            'imgs/missing.svg',
            '../outside.svg',
            'imgs/../outside.svg',
            'imgs/riff\x00.svg',
            str(outside_image),
            'https://example.com/image.svg',
            'imgs/notes.txt',
            {'caption': 'missing source'},
            42,
        ]
        if symlink_entry:
            entries.append(symlink_entry)

        with self.assertLogs('track_renderer', level='WARNING'):
            html = track_renderer.build_images_html(
                {'images': entries}, str(self.track_path))

        self.assertEqual('', html)

    def test_skips_non_list_images(self):
        with self.assertLogs('track_renderer', level='WARNING'):
            html = track_renderer.build_images_html(
                {'images': {'imgs/riff1.svg'}}, str(self.track_path))

        self.assertEqual('', html)

    def test_build_page_follows_images_display_order(self):
        html = track_renderer._build_page(
            title='Track',
            notes='',
            gig_id=0,
            semitones=0,
            display=['images', 'structure'],
            leadsheet_html='',
            keyboard_svg='',
            table_html='<table id="structure"></table>',
            images_html='<div id="images"></div>',
        )

        self.assertLess(html.index('id="images"'), html.index('id="structure"'))

    def test_render_chart_renders_images_when_selected(self):
        image_data = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        (self.image_dir / 'riff1.svg').write_bytes(image_data)
        self.track_path.write_text(
            '{"display": ["images"], "images": [{"caption": "riff1", '
            '"source": "imgs/riff1.svg"}]}',
            encoding='utf-8')

        html = track_renderer.render_chart(0, str(self.track_path))
        encoded = base64.b64encode(image_data).decode('ascii')

        self.assertIn('class="track-images"', html)
        self.assertIn('class="track-image-caption">riff1</div>', html)
        self.assertIn('data:image/svg+xml;base64,{}'.format(encoded), html)

    def test_render_chart_ignores_images_outside_display(self):
        image_data = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        (self.image_dir / 'riff1.svg').write_bytes(image_data)
        self.track_path.write_text(
            '{"display": [], "images": ["imgs/riff1.svg"]}',
            encoding='utf-8')

        html = track_renderer.render_chart(0, str(self.track_path))

        self.assertNotIn('track-images', html)
        self.assertNotIn('data:image/svg+xml', html)


if __name__ == '__main__':
    unittest.main()
