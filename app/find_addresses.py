import re

road_types = [
    "road",
    "rd\.",
    "way",
    "street",
    "st\.",
    "avenue",
    "av\.",
    "ave\.",
    "boulevard",
    "blvd.",
    "lane",
    "ln\.",
    "drive",
    "dr\.",
    "terrace",
    "ter.",
    "place",
    "pl.",
    "court",
    "ct.",
    "park\.",
    "parkway",
    "pkwy"]

street_address = re.compile(
    '\d{1,4} [\w\s]{1,20}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\W?(?=\s|$)', re.IGNORECASE)


def strip_and_lower(string):
    return re.sub(r'([^\s\w]|_)+', "", string).lower().strip()


def find_addresses_in_sentence(sentence):
    return [strip_and_lower(x) for x in street_address.findall(sentence)]


def find_addresses_in_text(sections):
    data = []

    for groupIdx in range(len(sections)):
        group = sections[groupIdx]
        hasLastGroup = groupIdx > 0
        hasNextGroup = len(sections) - 1 > groupIdx
        lastGroup = sections[groupIdx - 1] if hasLastGroup else None
        nextGroup = sections[groupIdx + 1] if hasNextGroup else None

        groupCount = len(group["sentences"])
        for sentenceIdx in range(groupCount):
            addresses = find_addresses_in_sentence(
                group["sentences"][sentenceIdx])

            startSection = 0
            startSentence = 0
            endSection = 0
            endSentence = 0
            context = []

            CONTEXT = 3

            useLastGroup = (sentenceIdx < CONTEXT) & hasLastGroup
            useNextGroup = (sentenceIdx + CONTEXT > groupCount) & hasNextGroup

            if useLastGroup:
                startSection = groupIdx - 1
                startSentence = len(
                    lastGroup["sentences"]) - CONTEXT + sentenceIdx
            else:
                startSection = groupIdx
                startSentence = sentenceIdx - CONTEXT

            if useNextGroup:
                endSection = groupIdx + 1
                endSentence = sentenceIdx - groupCount + CONTEXT
            else:
                endSection = groupIdx
                endSentence = sentenceIdx + CONTEXT

            source = str(startSection) + "-" + str(startSentence) + \
                "." + str(endSection) + "-" + str(endSentence)

            if startSection == endSection:
                context = group["sentences"][startSentence:endSentence]
            elif useLastGroup:
                context = lastGroup["sentences"][startSentence:] + \
                    group["sentences"][:endSentence]
            elif useLastGroup:
                context = group["sentences"][startSentence:] + \
                    nextGroup["sentences"][:endSentence]

            for address in addresses:
                data.append({
                    "source": source,
                    "address": address,
                    "context": context
                })

    filtered = [d for d in data if any(
        " " + r in d["address"] for r in road_types)]
    filtered.sort()
    return filtered
