"""Package the inspected device; omit unlicensed research captures and caches."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def references():
    sources=[
      ('touch_display2_7inch.step.zip','https://pip-assets.raspberrypi.com/categories/1083-raspberry-pi-touch-display-2/documents/RP-009154-DD-3-raspberry-pi-touch-display-2-step-7inch.zip','Manufacturer 7-inch STEP download; MIT reference geometry, approximate fit guide.'),
      ('touch_display2_7inch_brief.pdf','https://pip-assets.raspberrypi.com/categories/1083-raspberry-pi-touch-display-2/documents/RP-010429-MM-3-touch-display-2-7-inch-product-brief.pdf','October 2026, 7-inch dimensions/mounting drawing and published 2.4W display consumption.'),
      ('pi4_mechanical.pdf','https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008343-DS-1-raspberry-pi-4-mechanical-drawing.pdf','85x56x1.6mm board, 58x49mm mounting pitch; connector envelopes.'),
      ('fan_infosheet.pdf','https://cdn.noctua.at/media/noctua_nf_a4x10_5v_pwm_infosheet_en_web.pdf?download=true','40x40x10mm; max 0.35W at 5V; 8.9m3/h free-air airflow; USB power adapter included.'),
      ('pi4_stock.html','https://www.pishop.us/product/raspberry-pi-4-model-b-2gb/','Live retail capture: SC0193, $67.50, in stock.'),
      ('display_stock.html','https://www.pishop.us/product/raspberry-pi-touch-display-2/','Live retail capture: SC1635, $81.95, in stock.'),
      ('keyboard_stock.html','https://www.adafruit.com/product/1736','285x123x22mm, 237.2g, $9.95, in stock.'),
      ('powerbank_stock.html','https://www.anker.com/products/a1259-built-in-cable-power-bank-10000mah','A1259, 104x52.3x26mm, 215g, 5V3A per USB-C output, $49.99, in stock.')]
    rows=[]
    for filename,url,basis in sources:
        p=ROOT/'sources'/filename
        rows.append({'url':url,'research_capture':filename,'capture_available_locally':p.is_file(),
          'capture_sha256':sha(p) if p.is_file() else None,'used_for':basis,
          'included_in_distribution':False,'copyright_note':'Linked primary source; research capture not redistributed.'})
    for url,basis in [
      ('https://www.raspberrypi.com/documentation/accessories/touch-display-2.html','Pi4 compatibility, 15-way DSI, GPIO power, auto-detection, desktop landscape orientation.'),
      ('https://www.raspberrypi.com/news/getting-started-with-raspberry-pi-touch-display-2/','Illustrated connector orientation and red physical pin2 / black pin6 power mapping.'),
      ('https://www.raspberrypi.com/documentation/hardware/raspberrypi/power.html','Pi4 recommended 5V3A, aggregate USB1.2A; older approximate current measurements used only as context.'),
      ('https://www.noctua.at/en/products/nf-a4x10-5v-pwm/specifications','5V PWM model: 32mm hole pitch, max0.07A, 8.9m3/h free-air.'),
      ('https://media.startech.com/cms/pdfs/usb2cc50cm_datasheet.pdf','USB2CC50CM: 0.5m,3A,22/30AWG; product width12mm,height6mm,20g.'),
      ('https://www.adafruit.com/product/824','300mm male/female extensions,28AWG; connector current rating not published.'),
      ('https://www.adafruit.com/product/1648','300x16mm standard15-way camera/display FFC,2g.'),
      ('https://www.raspberrypi.com/software/operating-systems/','Pi4-supported64-bitDesktopTrixie release2026-10-06; checksum reference, not a downloaded image.'),
      ('https://www.raspberrypi.com/documentation/computers/configuration.html','Current ControlCentre/Screens orientation workflow.')]:
        rows.append({'url':url,'used_for':basis,'access_method':'web tool primary source','raw_capture_redistributed':False})
    result={'checked_date':'2026-11-17','source_policy':'Primary manufacturer documentation and direct retail references; no supplier account or purchase.',
      'sources':rows,'redistributed_vendor_geometry':{'file':'touch_display2_7inch.step','sha256':sha(ROOT/'sources/touch_display2_7inch.step'),'license':'touch_display2_LICENSE.txt','copyright':'Raspberry Pi Ltd 2026; see included exact license'},
      'bom_urls':'../bom.json','price_and_stock_limit':'Dated reference US retail; no shipping destination checked. Generic hardware/consumables use dimensional specifications and explicit allowances.'}
    (ROOT/'sources/references.json').write_text(json.dumps(result,indent=2)+'\n')


def connection_drawing():
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="780" viewBox="0 0 1200 780">
<rect width="1200" height="780" fill="#eef1f4"/>
<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="none" stroke="#3b6580" stroke-width="1.5"/></marker></defs>
<g font-family="sans-serif" fill="#203345"><text x="45" y="55" font-size="30" font-weight="bold">FIELDDECK 7 · MODULE CONNECTIONS</text><text x="45" y="88" font-size="17">Digital connection plan · physical pin numbers · 5 V single-port supply</text>
<g fill="white" stroke="#7d929f" stroke-width="2"><rect x="45" y="180" width="250" height="145" rx="12"/><rect x="440" y="155" width="300" height="390" rx="12"/><rect x="900" y="160" width="255" height="160" rx="12"/><rect x="900" y="400" width="255" height="100" rx="12"/><rect x="45" y="425" width="250" height="105" rx="12"/></g>
<g font-size="20" font-weight="bold"><text x="65" y="215">Anker A1259</text><text x="460" y="195">Raspberry Pi 4 · SC0193</text><text x="920" y="195">Touch Display 2</text><text x="920" y="435">Adafruit 1736</text><text x="65" y="460">Noctua 5V PWM</text></g>
<g font-size="17"><text x="65" y="247">Separate USB-C output</text><text x="65" y="278">5 V / 3 A maximum</text><text x="460" y="255">USB-C power input</text><text x="460" y="305">DISPLAY · 15-way DSI</text><text x="460" y="355">GPIO physical pin 2 · 5 V</text><text x="460" y="390">GPIO physical pin 6 · GND</text><text x="460" y="452">Black USB 2 × 2</text><text x="460" y="500">Blue USB 3 × 2 + Ethernet</text><text x="920" y="225">SC1635 · 7-inch</text><text x="920" y="260">DSI + supplied J1 lead</text><text x="920" y="292">Red = 5 V · black = GND</text><text x="920" y="467">Wired USB keyboard</text><text x="65" y="495">Supplied NA-AC7 USB lead</text></g>
<g stroke="#3b6580" stroke-width="2.5" fill="none" marker-end="url(#arrow)"><path d="M295 250H440"/><path d="M740 300L900 235"/><path d="M740 355L820 355L900 275"/><path d="M740 390L840 390L900 297"/><path d="M900 450H740"/><path d="M295 475L440 445"/></g>
<g font-size="15"><text x="310" y="210">0.5 m USB-C</text><text x="766" y="225">300 mm FFC</text><text x="762" y="419">2 × 300 mm extension</text><text x="48" y="600">Power + touch/display data use separate connections. No custom PCB or PD voltage trigger.</text><text x="48" y="632">Rear USB service loops return through the I/O opening; keep fan rotor and FFC clear.</text><text x="48" y="664">Display extensions: retain and insulate both joins; contact rating / loaded voltage remain unverified.</text><text x="48" y="696">Available ports do not imply spare power: all USB ports share 1.2 A; the whole device shares bank 3 A.</text><text x="48" y="744" fill="#657789">Use CONNECTIONS.md for connector orientation, routing, current limits and future checks.</text></g></g></svg>'''
    (ROOT/'views/connections.svg').write_text(svg)
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode(),write_to=str(ROOT/'views/connections.png'))


def main():
    verification=json.loads((ROOT/'analysis/verification.json').read_text())
    require(verification['status']=='digital_geometry_checks_passed', 'Current geometry verification must pass.')
    require(verification['assembly_step_sha256']==sha(ROOT/'cad/FIELDDECK_7.step'), 'The verified assembly changed.')
    require(verification['author_cad_sha256']==sha(ROOT/'author_cad.py'), 'The verified CAD author changed.')
    verified=verification.get('verified_files_sha256')
    if not isinstance(verified,dict) or not verified:
        raise ValueError('A complete current exported-file verification is required.')
    geometry=json.loads((ROOT/'cad/geometry_report.json').read_text())
    expected_exports={'cad/FIELDDECK_7.step', 'cad/FIELDDECK_7.glb'}
    expected_exports.update('cad/print/'+part['name']+'.'+extension
                            for part in geometry['parts'] if part['printable']
                            for extension in ('step','stl'))
    actual_exports={str(path.relative_to(ROOT)) for path in (ROOT/'cad').rglob('*')
                    if path.is_file() and path.suffix.lower() in ('.step','.stl','.glb')}
    require(actual_exports==expected_exports, 'The CAD export inventory contains missing or unverified files.')
    required_verified=expected_exports | {
        'analysis/calculations.json', 'author_cad.py', 'bom.json', 'cad/geometry_report.json',
        'design.json', 'engineering.py', 'sources/touch_display2_7inch.step',
        'study_contract.py', 'verify_device.py'}
    if (ROOT/'requirements.json').is_file():
        required_verified.add('requirements.json')
    require(set(verified)==required_verified, 'The exported-file verification inventory is incomplete.')
    for name,digest in verified.items():
        path=ROOT/name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()) or sha(path)!=digest:
            raise ValueError('A verified artifact changed: '+name)
    from study_contract import validate_calculation_record
    validate_calculation_record(ROOT)
    check=json.loads((ROOT/'analysis/hs_source_check.json').read_text())['source_bundle_run']
    require(check['input_sources']['FIELDDECK_7.step']['sha256']=='sha256:'+sha(ROOT/'cad/FIELDDECK_7.step'), 'The saved HS source assembly is stale.')
    snapshot=json.loads((ROOT/'HS_PROJECT_SNAPSHOT.json').read_text())
    for name in ('bom.json','design.json'):
        selected=[s for s in snapshot['snapshot']['engineeringSources'] if s.get('metadata',{}).get('original_filename')==name]
        require(len(selected)==1 and selected[0]['content_hash']=='sha256:'+sha(ROOT/name), 'The saved HS source is stale: '+name)
    references();connection_drawing()
    include=[]
    for p in ROOT.rglob('*'):
        if p.is_symlink():
            raise ValueError('Distribution paths cannot contain symbolic links: '+str(p.relative_to(ROOT)))
        if not p.is_file():continue
        relative=p.relative_to(ROOT)
        if '__pycache__' in relative.parts or p.name.startswith('.') or p.name in ('MANIFEST.json','LICENSE.txt','FIELDDECK_7_DIGITAL.zip','FIELDDECK_7_DIGITAL.zip.sha256'):continue
        if relative.parts[0]=='sources' and p.name not in ('touch_display2_7inch.step','touch_display2_LICENSE.txt','references.json','downloads.json'):continue
        include.append(p)
    manifest={'device':'Fielddeck 7','scope':'digital engineering prototype only','files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(include)}}
    (ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    include.append(ROOT/'MANIFEST.json')
    archive=ROOT/'FIELDDECK_7_DIGITAL.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(include):z.write(p,'Fielddeck_7/'+str(p.relative_to(ROOT)))
        license_path=ROOT.parents[2]/'LICENSE'
        if not license_path.is_file():
            license_path=ROOT/'LICENSE.txt'
        z.write(license_path,'Fielddeck_7/LICENSE.txt')
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'The distribution ZIP has a corrupt entry.')
        for relative,digest in manifest['files'].items():
            require(hashlib.sha256(z.read('Fielddeck_7/'+relative)).hexdigest()==digest, 'The packaged artifact differs: '+relative)
    (ROOT/'FIELDDECK_7_DIGITAL.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
    print(json.dumps({'zip':str(archive.relative_to(ROOT)),'bytes':archive.stat().st_size,'verified_payload_files':len(manifest['files']),'sha256':sha(archive)}))


if __name__=='__main__':main()
