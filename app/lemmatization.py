from word_forms.word_forms import get_word_forms


def get_lemmas(word):
    other_forms = list(set([item for sublist in [list(x) for x in get_word_forms(
        word).values()] for item in sublist if item != word]))
    min_matching_len = max(len(word), 3)
    return [x for x in other_forms if (any(s.isupper() for s in x) == False) & (x[0:min_matching_len] == word[0:min_matching_len])]


def lcd_for_word(word, lemmas):
    if len(lemmas) == 0:
        return word
    all_forms = [word] + lemmas
    idx = 0
    while True:
        if len(set([word[:idx].lower() for word in all_forms])) != 1:
            return all_forms[0][:idx - 1]
        idx += 1
