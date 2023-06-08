from drbot import settings, log
import pandas as pd
import base64
import zlib
import json


class Converter:
    def __init__(self):
        self.wiki_notes = dict()
        self.cleaned_usernotes = dict()
        self.combined_notes = dict()
        self.df = pd.DataFrame()

    def add(self, wiki, notes):
        self.wiki_notes = wiki
        self.cleaned_usernotes = notes
        self.wiki_notes = self.combine_json()
        self.df = pd.DataFrame.from_dict(self.cleaned_usernotes)

    def empty_notes(func):
        def f(self):
            if not self.wiki_notes:
                raise Exception(f"Not authenticated or no information provided.")
            format_name = func(self)
            log.warning(f"{format_name} file created in current directory")

        return f

    def combine_json(self):
        self.wiki_notes['blob'] = self.cleaned_usernotes
        return self.wiki_notes.copy()

    def combinednotes(self):
        return self.wiki_notes

    @empty_notes
    def json_format(self):
        self.df.to_json('usernotes_json.json')
        return "JSON"

    @empty_notes
    def csv_format(self):
        self.df.to_csv('usernotes_csv.csv', encoding='utf-8', index=False)
        return "CSV"


class BlobDecoder:
    def pInflate(self, data) -> bytes:
        decompress = zlib.decompressobj(15)
        decompressed_data = decompress.decompress(data)
        decompressed_data += decompress.flush()
        return decompressed_data

    def b64d(self, data: str) -> bytes:
        return base64.b64decode(data)

    def js_byte_to_string(self, data: bytes) -> str:
        return data.decode("utf-8")
    def __init__(self):
        self.cleaned_notes = dict()
        self.notelength = int

    def blob_to_string(self, blob: str) -> dict:
        """Base64 -> zlib-compressed -> string -> dict"""
        # base64 decode blob
        zlib_bytes = self.b64d(str.encode(blob))

        # zlib-uncompress to byte
        decompressed_bytes = self.pInflate(zlib_bytes)

        # byte to string
        clean_string = self.js_byte_to_string(decompressed_bytes)

        # Return dict
        self.cleaned_notes = json.loads(clean_string)

        # sum of values to get total
        note_count = [len(x['ns']) for x in self.cleaned_notes.values()]
        self.notelength = sum(note_count)

        return self.cleaned_notes

    def conv_blob(self) -> dict:
        return self.cleaned_notes

    def note_length(self) -> int:
        return self.notelength