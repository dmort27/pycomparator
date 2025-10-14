#!/usr/bin/env python3

import sqlite3
import re
import panphon
import panphon.sonority
import collections

ENG_CONFL = {
    9: 9,
    8: 9,
    7: 7,
    6: 6,
    5: 5,
    4: 4,
    3: 4,
    2: 4,
    1: 4,
}

TUSOM = {
    9: 9,
    8: 9,
    7: 7,
    6: 6,
    5: 5,
    4: 4,
    3: 3,
    2: 2,
    1: 1
}

class Syllabify:
    def __init__(self, confl=ENG_CONFL, no_onsetless=False):
        self.ft = panphon.FeatureTable()
        self.son = panphon.sonority.Sonority()
        self.confl = confl
        self.no_onsetless = no_onsetless

    def _sonority(self, ph):
        return self.confl[self.son.sonority(ph)]

    def _to_grid(self, word):
        Seg = collections.namedtuple('Seg', 'ph son')
        segs = self.ft.ipa_segs(word)
        return [Seg(ph, self._sonority(ph)) for ph in segs]

    def find_boundaries(self, grid):
        peaks = []
        for i, seg in enumerate(grid):
            if seg.son >= 8:
                peaks.append(i)
        boundaries = [True for _ in grid] + [True]
        if peaks:
            for i, _ in list(enumerate(boundaries))[1:-1]:
                if i < peaks[0] or i > peaks[-1]:
                    boundaries[i] = False
                if grid[i-1].son < grid[i].son:
                    boundaries[i] = False
                if grid[i-1].son > grid[i].son:
                    if i < len(grid) - 1 and grid[i].son >= grid[i+1].son:
                        boundaries[i] = False
                    elif i == len(grid) - 1:
                        boundaries[i] = False
                try:
                    if grid[i-2].son == grid[i-1].son and grid[i-1].son == grid[i].son:
                        boundaries[i] = False
                except IndexError:
                    pass
                if self.no_onsetless and i < len(grid) - 1:
                    print('long enough')
                    if grid[i].son > 7 and grid[i+1].son > 7:
                        print('two vowels')
                        boundaries[i] = False
        return boundaries

    def _syl_seg(self, word):
        grid = self._to_grid(word)
        b = self.find_boundaries(grid)
        syls, syl = [], []
        for i, _ in enumerate(grid):
            if b[i] and syl:
                syls.append(syl)
                syl = []
            syl.append(grid[i])
        syls.append(syl)
        return syls

    def syl_seg(self, word):
        return [''.join([seg.ph for seg in syl]) for syl in self._syl_seg(word)]

    def parse_syl(self, syl):
        if syl:
            max_son = max([seg.son for seg in syl])
            ons, nuc, cod = '', '', ''
            i = 0
            while syl[i].son < max_son:
                ons += syl[i].ph
                i += 1
            nuc = syl[i].ph
            i += 1
            cod = ''.join([seg.ph for seg in syl[i:]])
            Syl = collections.namedtuple('Syl', 'ons nuc cod')
            return Syl(ons, nuc, cod)
        else:
            Syl = collections.namedtuple('Syl', 'ons nuc cod')
            return Syl('', '', '')

    def syl_parse(self, word):
        syls = self._syl_seg(word)
        return [self.parse_syl(s) for s in syls]

syllabify = Syllabify()    
forms = []
conn = sqlite3.connect('borderlands.sqlite3')
cur = conn.cursor()
cur.execute('SELECT form FROM reflexes WHERE langid<5')
rows = cur.fetchall()
for row in rows:
    these_forms = re.split('[ -]', row[0])
    these_syls = [syllabify.syl_seg(x) for x in these_forms]
    these_forms = [x for xs in these_syls for x in xs]
    forms = forms + these_forms

forms = set(forms)

print('\n'.join(forms))