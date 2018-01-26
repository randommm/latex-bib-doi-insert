#Copyright Marco Inacio <software@marcoinacio.com> 2018,
#David Kiliani <mail@davidkiliani.de> 2011-2014,
#Bruno Nicenboim <https://github.com/bnicenboim> 2014
#licensed under GNU GPL version 3

#Based on (i.e. uses code from)
#the doi_finder.py made by
#David Kiliani and Bruno Nicenboim:
#https://github.com/torfbolt/DOI-finder
#(which was also GNU GPL 3 licensed)

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, version 3 of the License.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import requests
import subprocess
import sys
import codecs
from pybtex.database.input import bibtex
import os
import re
from urllib.parse import quote_plus

def insert_doi(file_str, key, doi):
    return file_str.replace(key + ",\n", key + ",\n  doi = {" + doi + "},\n")

def detex(tex_str):
    '''
    Remove any tex markup from the string. This calls the external
    program detex.
    @param tex_str: the string to be cleaned.
    '''
    prog = subprocess.Popen(["detex"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    return prog.communicate(tex_str.encode())[0]

def fuzzy_match(orig, sub):
    '''
    Do a fuzzy match of two strings. Returns the amount of word pairs
    in the substring that also appear in the original string.
    @param orig: the original string to be searched.
    @param sub: the substring to look for in orig.
    '''
    orig = re.sub(r'[^a-zA-Z0-9 ]+', '', orig)
    sub = re.sub(r'[^a-zA-Z0-9 ]+', '', sub)
    sub = sub.lower().split()
    pairs = [" ".join(sub[i:i+2]) for i in range(len(sub) - 1)]
    match = [len(p) for p in pairs if p in orig.lower()]
    return float(sum(match))/len("".join(pairs))


def process_author_field(author_raw):
    add = ""
    author = ""
    for i, aut in enumerate(author_raw):
        author += add
        if "family" in aut.keys():
            author += aut['family']
        if "given" in aut.keys():
            author += ", " + aut['given']
        add = " and "

    return author

def search_by_doi(doi):
    r = requests.get('https://api.crossref.org/works/'
                     + quote_plus(doi))
    res_obj = r.json()
    assert res_obj['status'] == "ok"
    title = res_obj["message"]["title"][0]
    title = res_obj["message"]["title"][0]
    author = process_author_field(res_obj["message"]["author"])

    return dict(title=title, author=author)

def search_by_title_and_author(title, author):
    r = requests.get(
            'https://api.crossref.org/works?'
            +
            'query.title=' + quote_plus(title) + '&'
            +
            'query.author=' + quote_plus(author)
            +
            '&sort=score&order=desc&rows=1'
            )
    res_obj = r.json()
    if (res_obj['status'] != "ok" or
        not len(res_obj['message']['items'])):
        return None

    item = res_obj['message']['items'][0]
    title = item["title"][0]
    doi = item["DOI"]
    author = process_author_field(item["author"])

    return dict(title=title, author=author, doi=doi)

def bibfile_process(bibfile_name):
    parser = bibtex.Parser()
    bib_data = parser.parse_file(bibfile_name)
    bib_sorted = sorted(list(bib_data.entries.items()), key=lambda x: x[0])
    #bib_sorted = [x for x in bib_sorted if not 'doi' in x[1].fields]
    bibfile = codecs.open(bibfile_name, 'r', encoding='utf-8')
    file_str = str().join(bibfile.readlines())
    bibfile.close()

    for key, value in bib_sorted[:]:
        try:
            author = detex(value.fields['author']).decode()
            title = detex(value.fields['title']).decode()
        except KeyError:
            continue
        try:
            journal = value.fields['journaltitle']
        except KeyError:
            try:
                journal = value.fields['journal']
            except KeyError:
                journal = ""
        try:
            doi = value.fields['doi']
        except KeyError:
            doi = ""

        if doi:
            res = search_by_doi(doi)
            print("Already has DOI:")
            print("Current title:", title)
            print("Crossref title:", res["title"])
            print("Current authors:", author)
            print("Crossref authors:", res["author"])
        else:
            res = search_by_title_and_author(title, author)

            if res is None:
                print("DOI not found for:")
                print("Current title:", title)
                print("Current authors:", author)
            else:
                print("Found DOI for:")
                print("DOI:", res["doi"])
                print("Current title:", title)
                print("Crossref title:", res["title"])
                print("Current authors:", author)
                print("Crossref authors:", res["author"])

                title_sim = fuzzy_match(res["title"], title)
                author_sim = fuzzy_match(res["author"], author)
                if title_sim <= 0.5 or author_sim <= 0.5:
                    print("DOI not inserted (names diverge)!")
                elif title_sim >= 0.9 and author_sim >= 0.9:
                    file_str = insert_doi(file_str, key, res["doi"])
                    print("DOI inserted automatically!")
                else:
                    resp = None
                    while resp != "y" and resp != "n":
                        print("Set this DOI? (y/n)")
                        resp = input()
                        if resp == 'y':
                            file_str = insert_doi(file_str, key, res["doi"])
                            print("DOI inserted!")
                        elif resp == 'n':
                            print("DOI NOT inserted!")

                bibfile = codecs.open(bibfile_name + ".out", 'w', encoding='utf-8')
                bibfile.write(file_str)
                bibfile.close()

        print("----------------------")


if __name__ == '__main__':
    argv = sys.argv
    if len(argv) >= 2:
        bib = argv[1]
    else:
        bib = input("input file:")

    bibfile = "%s/%s" % ( os.getcwd(),bib) if not os.path.isfile(bib) else bib
    bibfile_process(bibfile)
