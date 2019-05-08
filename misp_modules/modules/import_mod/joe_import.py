# -*- coding: utf-8 -*-
from pymisp import MISPEvent, MISPObject
import json
import base64

misperrors = {'error': 'Error'}
userConfig = {}
inputSource = ['file']

moduleinfo = {'version': '0.1', 'author': 'Christian Studer',
              'description': 'Import for Joe Sandbox JSON reports',
              'module-type': ['import']}

moduleconfig = []

file_object_fields = ['filename', 'md5', 'sha1', 'sha256', 'sha512', 'ssdeep']
file_object_mapping = {'entropy': ('float', 'entropy'),
                       'filesize': ('size-in-bytes', 'size-in-bytes'),
                       'filetype': ('mime-type', 'mimetype')}
pe_object_fields = {'entrypoint': ('text', 'entrypoint-address'),
                    'imphash': ('imphash', 'imphash')}
pe_object_mapping = {'CompanyName': 'company-name', 'FileDescription': 'file-description',
                     'FileVersion': 'file-version', 'InternalName': 'internal-filename',
                     'LegalCopyright': 'legal-copyright', 'OriginalFilename': 'original-filename',
                     'ProductName': 'product-filename', 'ProductVersion': 'product-version',
                     'Translation': 'lang-id'}
section_object_mapping = {'characteristics': ('text', 'characteristic'),
                          'entropy': ('float', 'entropy'),
                          'name': ('text', 'name'), 'rawaddr': ('hex', 'offset'),
                          'rawsize': ('size-in-bytes', 'size-in-bytes'),
                          'virtaddr': ('hex', 'virtual_address'),
                          'virtsize': ('size-in-bytes', 'virtual_size')}
signerinfo_object_mapping = {'sigissuer': ('text', 'issuer'),
                             'version': ('text', 'version')}


class JoeParser():
    def __init__(self, data):
        self.data = data
        self.misp_event = MISPEvent()

    def parse_joe(self):
        self.parse_fileinfo()
        self.finalize_results()

    def parse_fileinfo(self):
        fileinfo = self.data['fileinfo']
        file_object = MISPObject('file')
        for field in file_object_fields:
            file_object.add_attribute(field, **{'type': field, 'value': fileinfo[field]})
        for field, mapping in file_object_mapping.items():
            attribute_type, object_relation = mapping
            file_object.add_attribute(object_relation, **{'type': attribute_type, 'value': fileinfo[field]})
        pe_object = MISPObject('pe')
        file_object.add_reference(pe_object.uuid, 'included-in')
        self.misp_event.add_object(**file_object)
        peinfo = fileinfo['pe']
        for field, mapping in pe_object_fields.items():
            attribute_type, object_relation = mapping
            pe_object.add_attribute(object_relation, **{'type': attribute_type, 'value': peinfo[field]})
        pe_object.add_attribute('compilation-timestamp', **{'type': 'datetime', 'value': int(peinfo['timestamp'].split()[0], 16)})
        program_name = fileinfo['filename']
        for feature in peinfo['versions']['version']:
            name = feature['name']
            if name == 'InternalName':
                program_name = feature['value']
            pe_object.add_attribute(pe_object_mapping[name], **{'type': 'text', 'value': feature['value']})
        sections_number = len(peinfo['sections']['section'])
        pe_object.add_attribute('number-sections', **{'type': 'counter', 'value': sections_number})
        for section in peinfo['sections']['section']:
            section_object = self.parse_pe_section(section)
            pe_object.add_reference(section_object.uuid, 'included-in')
            self.misp_event.add_object(**section_object)
        signerinfo_object = MISPObject('authenticode-signerinfo')
        pe_object.add_reference(signerinfo_object.uuid, 'signed-by')
        self.misp_event.add_object(**pe_object)
        signerinfo_object.add_attribute('program-name', **{'type': 'text', 'value': program_name})
        signatureinfo = peinfo['signature']
        for feature, mapping in signerinfo_object_mapping.items():
            attribute_type, object_relation = mapping
            signerinfo_object.add_attribute(object_relation, **{'type': attribute_type, 'value': signatureinfo[feature]})
        self.misp_event.add_object(**signerinfo_object)

    def parse_pe_section(self, section):
        section_object = MISPObject('pe-section')
        for feature, mapping in section_object_mapping.items():
            attribute_type, object_relation = mapping
            section_object.add_attribute(object_relation, **{'type': attribute_type, 'value': section[feature]})
        return section_object

    def finalize_results(self):
        event = json.loads(self.misp_event.to_json())['Event']
        self.results = {key: event[key] for key in ('Attribute', 'Object') if (key in event and event[key])}


def handler(q=False):
    if q is False:
        return False
    q = json.loads(q)
    data = base64.b64decode(q.get('data')).decode('utf-8')
    if not data:
        return json.dumps({'success': 0})
    joe_data = json.loads(data)['analysis']
    print(type(joe_data))
    joe_parser = JoeParser(joe_data)
    joe_parser.parse_joe()
    return {'results': joe_parser.results}


def introspection():
    modulesetup = {}
    try:
        userConfig
        modulesetup['userConfig'] = userConfig
    except NameError:
        pass
    try:
        inputSource
        modulesetup['inputSource'] = inputSource
    except NameError:
        pass
    modulesetup['format'] = 'misp_standard'
    return modulesetup


def version():
    moduleinfo['config'] = moduleconfig
    return moduleinfo
