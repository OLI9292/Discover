from elasticsearch import Elasticsearch
from elasticsearch import helpers
import re

from data.manhattan_streets_without_road_types import manhattan_streets_without_road_types
from data.stop_words import stop_words

es = Elasticsearch(
    ["https://ee2174119d634def91a0a4b2a91c19e4.us-east-1.aws.found.io:9243"],
    http_auth=('elastic', '3y44M8nGXMrppI9OQWikcxZZ')
)

BAD_STRINGS = ["published", "acknowledgments"]
COMMON_ROAD_TYPES = ["street", "avenue", "road"]

CONTEXT = 3


def is_not_using_citation(address, groups, should_print=False):
    number = int(address.split(" ")[0])

    look_for = (str(number - 1), str(number + 1))

    if (number < 10) | any(" " + r in address.lower() for r in COMMON_ROAD_TYPES):
        return True

    split = " ".join(groups).lower().split(address.lower())
    result = (look_for[0] not in split[0]) | (look_for[1] not in split[1])
    if (result == False) & should_print:
        print "bad: " + address
    return result


def is_not_figure(sentence, address):
    return re.match(r'.*[Ff]igure [0-9]+\.$', sentence.split(address)[0], flags=re.DOTALL) == None


def is_year(string):
    try:
        return (int(string) > 1850) & (int(string) < 2020)
    except ValueError:
        return False


def matches_street(string, street):
    try:
        idx = string.index(street)
        next_char = string[idx + len(street)]
        return next_char.isalpha() == False
    except ValueError:
        return False
    except IndexError:
        return True


def is_from_manhattan(string, is_address):
    streets = [s for s in manhattan_streets_without_road_types if matches_street(
        string, " " + s if is_address else s)]
    return len(streets) > 0


def is_good_address(address):
    address = address.lower()
    if address[0] == "0":
        return False
    if any(s in address for s in stop_words):
        return False
    if len(address) < 7:
        return False
    if (address[4] == " ") & is_year(address[:4]):
        return False
    if len([char for char in address if char.isalpha()]) < 6:
        return False
    return is_from_manhattan(address, True)


def find_addresses_in_sentence(text):
    addresses = re.findall(
        r'\d{1,4} \b[A-Z][a-z]+\b(?:\s+[A-Z][a-z]+\b)*', text)
    return [a for a in addresses if is_good_address(a)]


def find_addresses_in_text(index, _id, size=1000):
    query = {"query": {"parent_id": {"type": "passage", "id": _id}}}
    hits = es.search(index=index, body=query, size=size)
    hits = hits["hits"]["hits"]

    all_addresses = []

    for idx in range(len(hits)):
        group = hits[idx]["_source"]["sentences"]

        if (idx < 10) & any(s in " ".join(group).lower() for s in BAD_STRINGS):
            continue

        has_last_group = idx > 0
        has_next_group = len(hits) - 1 > idx
        last_group = hits[idx -
                          1]["_source"]["sentences"] if has_last_group else []
        next_group = hits[idx +
                          1]["_source"]["sentences"] if has_next_group else []
        groups = last_group + group + next_group

        for sentence_idx in range(len(group)):
            addresses = find_addresses_in_sentence(group[sentence_idx])
            addresses = [{
                "address": address,
                "section": idx,
                "sentence": sentence_idx
            } for address in addresses if is_not_using_citation(address, groups) & is_not_figure(group[sentence_idx], address)]
            all_addresses += addresses

    return all_addresses
