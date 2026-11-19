"""Collect public document assets for the existing offline research import."""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import http.client
import ipaddress
import socket
from pathlib import Path
import re
import ssl
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urljoin


MIB = 1024 * 1024
IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^\s)]+)\)")


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # Connect to the checked IP directly, retaining TLS verification for the hostname.
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        if not addresses or not all(ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError('Non-public network address refused')
        raw = socket.create_connection((addresses[0][4][0], self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch(url, maximum, kinds):
    import certifi

    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or '.' not in parsed.hostname
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or parsed.hostname.endswith(('.local', '.internal'))):
        raise ValueError('Use a public HTTPS URL without credentials, query or fragment')
    context = ssl.create_default_context(cafile=certifi.where())
    connection = PublicHTTPSConnection(parsed.hostname, timeout=12, context=context)
    try:
        connection.request('GET', parsed.path or '/', headers={'User-Agent': 'LocalDocumentIntake/1.0'})
        with connection.getresponse() as response:
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}; redirects are not followed')
            kind = response.headers.get_content_type()
            if kind not in kinds:
                raise ValueError(f'Unexpected response type: {kind}')
            data = response.read(maximum + 1)
            if not data or len(data) > maximum:
                raise ValueError('Response empty or exceeds byte limit')
            return data, kind
    finally:
        connection.close()


def save(folder, name, data, url):
    (folder / name).write_bytes(data)
    return dict(file=name, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def web(args, folder):
    from trafilatura import bare_extraction, extract

    html, _ = fetch(args.url, 2 * MIB, {'text/html', 'application/xhtml+xml'})
    options = dict(url=args.url, include_comments=False, include_links=True,
                   include_images=True, include_formatting=True)
    document = bare_extraction(html, with_metadata=True, **options)
    markdown = extract(html, output_format='markdown', **options)
    if not document or not markdown or not document.title:
        raise ValueError('No usable article title or body')
    assets = []
    images = {}

    def localize(match):
        alt, src = match.groups()
        url = urljoin(args.url, src)
        if url not in args.image_url:
            return alt
        if url not in images:
            data, kind = fetch(url, 3 * MIB, {'image/png', 'image/jpeg', 'image/webp', 'image/gif'})
            signatures = {'image/png': (b'\x89PNG\r\n\x1a\n', '.png'),
                          'image/jpeg': (b'\xff\xd8\xff', '.jpg'),
                          'image/gif': (b'GIF8', '.gif'), 'image/webp': (b'RIFF', '.webp')}
            signature, suffix = signatures[kind]
            if not data.startswith(signature) or (kind == 'image/webp' and data[8:12] != b'WEBP'):
                raise ValueError('Image bytes do not match response type')
            name = f'image-{len(images) + 1}{suffix}'
            images[url] = name
            assets.append(save(folder, name, data, url))
        return f'![{alt}]({images[url]})'

    markdown = IMAGE.sub(localize, markdown)
    if set(args.image_url) - images.keys():
        raise ValueError('Requested image URL was not present in the extracted article')
    return document.title, markdown, assets, 'Trafilatura public HTML', document.sitename


def arxiv(args, folder):
    from pypdf import PdfReader

    paper = args.id
    if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})v[1-9]\d*', paper):
        raise ValueError('Provide an arXiv ID with an explicit version, e.g. 1706.03762v7')
    args.url = f'https://arxiv.org/abs/{paper}'
    pdf_url = f'https://arxiv.org/pdf/{paper}'
    bib_url = f'https://arxiv.org/bibtex/{paper}'
    pdf, _ = fetch(pdf_url, 12 * MIB, {'application/pdf'})
    bib, _ = fetch(bib_url, 64 * 1024, {'text/plain', 'application/x-bibtex'})
    citation = bib.decode('utf-8')
    base_id = paper.rsplit('v', 1)[0]
    if not citation.lstrip().startswith('@') or not re.search(
        r'\beprint\s*=\s*[{"]' + re.escape(base_id) + r'(?:v\d+)?[}"]', citation, re.I
    ):
        raise ValueError('BibTeX does not identify the requested arXiv paper')
    if not pdf.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF signature')
    reader = PdfReader(BytesIO(pdf), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
        raise ValueError('Expected an unencrypted PDF of 1–100 pages')
    sections = [f'## PDF page {i}\n\n{page.extract_text().strip()}'
                for i, page in enumerate(reader.pages, 1)]
    if not any(section.split('\n\n', 1)[1] for section in sections):
        raise ValueError('No extractable PDF text')
    title = re.search(r'\btitle\s*=\s*[{"]([^\n]+?)[}"],?\s*$', citation, re.M | re.I)
    assets = [save(folder, 'paper.pdf', pdf, pdf_url), save(folder, 'citation.bib', bib, bib_url)]
    return (title[1] if title else paper), '\n\n'.join(sections), assets, 'arXiv versioned PDF and pypdf text extraction', 'arXiv'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    page = modes.add_parser('web')
    page.add_argument('url')
    page.add_argument('--image-url', action='append', default=[])
    paper = modes.add_parser('arxiv')
    paper.add_argument('id')
    for mode in (page, paper):
        mode.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Output must be a new directory')
    if args.mode == 'web' and len(args.image_url) > 4:
        parser.error('At most four explicitly chosen image URLs')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output.parent) as temporary:
        folder = Path(temporary)
        title, markdown, assets, method, publisher = (web if args.mode == 'web' else arxiv)(args, folder)
        raw = (markdown.rstrip() + '\n').encode('utf-8')
        if len(raw) > 5 * MIB or b'\x00' in raw or '\ufffd' in markdown:
            raise ValueError('Invalid or oversized Markdown snapshot')
        assets.append(save(folder, 'source.md', raw, args.url))
        manifest = dict(url=args.url, title=title, retrieved_at=datetime.now(timezone.utc).isoformat(),
                        capture_method=method, format='markdown', file='source.md', publisher=publisher)
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        (folder / 'assets.json').write_text(json.dumps(assets, ensure_ascii=False, indent=2))
        args.output.mkdir()
        try:
            for path in folder.iterdir():
                path.rename(args.output / path.name)
        except OSError:
            for path in args.output.iterdir():
                path.unlink()
            args.output.rmdir()
            raise
    print(json.dumps({'manifest': str(args.output / 'manifest.json'), 'assets': assets}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, http.client.HTTPException) as error:
        raise SystemExit(str(error)) from None
