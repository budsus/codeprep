import logging
import sys

import argparse
from typing import List, Dict

from tqdm import tqdm

from dataprep.bpepkg.merge import MergeList, read_merges

logger = logging.getLogger(__name__)


class BpeData(object):
    def __init__(self, merges_cache=None, merges: MergeList=None):
        self.merges_cache = merges_cache
        self.merges = merges


ESCAPE_CHAR = '@'

ESCAPABLE_CHAR_LIST = [] + [ESCAPE_CHAR]


def escape(word: str, merged: bool=False) -> str:
    word = word.replace(ESCAPE_CHAR, 2 * ESCAPE_CHAR)
    if merged:
        return f"{word}{ESCAPE_CHAR}"
    else:
        return f"{word} {ESCAPE_CHAR}"


def unescape(parts: List[str]):
    if parts[-1][-1] != ESCAPE_CHAR:
        raise ValueError(f"There should be {ESCAPE_CHAR} at the end, however this is what was passed: {parts}")

    parts[-1] = parts[-1][:-1]
    return list(map(lambda p: p.replace(ESCAPE_CHAR + '@', ESCAPE_CHAR), parts))


def to_char_list(word: str):
    i = 0
    res = []
    while i < len(word):
        if word[i] != ESCAPE_CHAR or i+1 == len(word):
            res.append(word[i])
            i += 1
        elif word[i+1] in ESCAPABLE_CHAR_LIST:
            res.append(word[i:i+2])
            i += 2
        else:
            raise ValueError(f"Illegal escape sequence: {word[i:i+2]}")
    return res


def encode(words: Dict[str, int], merges: MergeList) -> Dict[str, int]:
    letters_list = {" ".join(to_char_list(k)): v for k, v in words.items()}

    new_letters_list = {}
    for letters, freq in letters_list.items():
        subwords = letters.split(" ")
        if len(subwords) > 5000:
            logger.warning(f'Encountered a string of length {len(subwords)}. It will take a while to bpe-encode it.')
            merges = tqdm(merges)
        for merge in merges:
            subwords_after_this_merge_round = []
            i = 0
            while i < len(subwords) - 1:
                if merge.pair == (subwords[i], subwords[i + 1]):
                    subwords_after_this_merge_round.append(subwords[i] + subwords[i + 1])
                    i += 2
                else:
                    subwords_after_this_merge_round.append(subwords[i])
                    i += 1
            if i == len(subwords) - 1:
                subwords_after_this_merge_round.append(subwords[-1])
            subwords = subwords_after_this_merge_round

        new_letters_list[" ".join(subwords)] = freq
    return new_letters_list


def encode_word(word: str, merges: MergeList) -> List[str]:
    '''
    :param word: token to be bpe encoded. Must terminate with @.
    '''
    enc_word, _ = encode({word: 0}, merges).popitem()
    subwords = enc_word.split(" ")
    return subwords


def get_bpe_subwords(word: str, bpe_data: BpeData) -> List[str]:
    merges = bpe_data.merges
    cache = bpe_data.merges_cache
    word = escape(word, merged=True)
    if word in cache:
        result = cache[word]
    else:
        result = encode_word(word, merges)

    return unescape(result)


__all__ = [encode, encode_word]


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('merges-file', action='store', help='path to file with merges')
    arg_parser.add_argument('word', action='store', help='word to encode', default='if')

    args = arg_parser.parse_args()

    merges = read_merges(args.merges_file)

    subwords = encode_word(args.word, merges)
    print(subwords)
