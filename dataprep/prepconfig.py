"""
This module encapsulate all the tricky ilogic of encoding preprocessing options into e.g. 30100
"""

import logging
from enum import Enum

from typing import Dict, List, Type, Callable, Optional

from dataprep.bpepkg.bpe_encode import BpeData, get_bpe_subwords
from dataprep.model.containers import SplitContainer, StringLiteral, OneLineComment, MultilineComment
from dataprep.model.noneng import NonEng
from dataprep.model.numeric import Number
from dataprep.model.whitespace import NewLine, Tab
from dataprep.model.word import Word

from dataprep.preprocess.core import ReprConfig

logger = logging.getLogger(__name__)


class PrepParam(str, Enum):
    EN_ONLY: str = 'enonly'
    COM_STR: str = 'comstr'
    SPLIT: str = 'split'
    TABS_NEWLINES: str = 'tabsnewlines'
    CAPS: str = 'caps'


class PrepConfig(object):
    possible_param_values = {
        PrepParam.EN_ONLY: [0, 3],
        PrepParam.COM_STR: [0, 1, 2, 3],
        PrepParam.SPLIT: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        PrepParam.TABS_NEWLINES: [0, 1],
        PrepParam.CAPS: [0, 1]
    }

    human_readable_values = {
        PrepParam.EN_ONLY: {0: 'multilang',
                            3: 'asci_only'},
        PrepParam.COM_STR: {0: 'strings+comments',
                            1: 'NO_strings+comments',
                            2: 'NO_strings+NO_comments',
                            3: 'strings+NO_comments'},
        PrepParam.SPLIT: {0: 'NO_splitting',
                          1: 'camel+underscore',
                          2: 'camel+underscore+numbers',
                          3: 'ronin',
                          4: 'camel+underscore+bpe_5k',
                          5: 'camel+underscore+bpe_1k',
                          6: 'camel+underscore+bpe_10k',
                          7: 'camel+underscore+bpe_20k',
                          8: 'camel+underscore+bpe_0',
                          9: 'camel+underscore+bpe_custom'},
        PrepParam.TABS_NEWLINES: {0: 'tabs+newlines',
                                  1: 'NO_tabs+NO_newlines'},
        PrepParam.CAPS: {
            0: 'case_preserved',
            1: 'lowercased'
        }
    }

    base_bpe_mask = {
        PrepParam.EN_ONLY: 0,
        PrepParam.COM_STR: 0,
        PrepParam.SPLIT: 1,
        PrepParam.TABS_NEWLINES: 0,
    }

    @staticmethod
    def __check_param_number(n_passed_params: int):
        n_expected_params = len([i for i in PrepParam])
        if n_passed_params != n_expected_params:
            raise ValueError(f'Expected {n_expected_params} params, got {n_passed_params}')

    @classmethod
    def from_encoded_string(cls, s: str):
        PrepConfig.__check_param_number(len(s))

        res = {}
        for ch, pp in zip(s, PrepParam):
            res[pp] = int(ch)
        return cls(res)

    @staticmethod
    def __check_invariants(params: Dict[PrepParam, int]):
        PrepConfig.__check_param_number(len(params))
        for pp in PrepParam:
            if params[pp] not in PrepConfig.possible_param_values[pp]:
                raise ValueError(f'Invalid value {params[pp]} for prep param {pp}, '
                                 f'possible values are: {PrepConfig.possible_param_values[pp]}')

        if params[PrepParam.CAPS] == 1 and params[PrepParam.SPLIT] == 0:
            raise ValueError("Combination NO_SPL=0 and CAPS=1 is not supported: "
                             "basic splitting needs to be dont done to lowercase the subword.")

        if params[PrepParam.CAPS] == 1 and params[PrepParam.SPLIT] == 3:
            raise ValueError("Combination NO_SPL=3 and CAPS=1 is not supported: "
                             "basic splitting needs to be dont done to lowercase the subword.")

    def __init__(self, params: Dict[PrepParam, int]):
        PrepConfig.__check_invariants(params)

        self.params = params

    def __str__(self) -> str:
        res = ""
        for k in PrepParam:
            res += str(self.params[k])
        return res

    def __repr__(self):
        return str(self.params)

    def get_param_value(self, param: PrepParam) -> int:
        return self.params[param]

    def get_base_bpe_prep_config(self):
        res = PrepConfig.base_bpe_mask
        res[PrepParam.CAPS] = self.params[PrepParam.CAPS]
        return str(PrepConfig(res))

    def __eq__(self, other):
        return self.params == other.params

    def get_number_splitter(self) -> Callable[[str, BpeData], List[str]]:
        split_param_value = self.get_param_value(PrepParam.SPLIT)
        if split_param_value in [0, 1]:
            return lambda s,c: [s]
        elif split_param_value in [2, 3]:
            return lambda s,c: [ch for ch in s]
        elif split_param_value in [4, 5, 6, 7, 8, 9]:
            return lambda s,c: get_bpe_subwords(s, c)
        else:
            raise ValueError(f"Invalid SPLIT param value: {split_param_value}")

    def get_word_splitter(self) -> Optional[Callable[[str, BpeData], List[str]]]:
        split_param_value = self.get_param_value(PrepParam.SPLIT)
        if split_param_value in [4, 5, 6, 7, 8, 9]:
            return lambda s, c: get_bpe_subwords(s, c)
        elif split_param_value in [1, 2]:
            return lambda s,c: [s]
        elif split_param_value in [0, 3]:
            return None
        else:
            raise ValueError(f"Invalid SPLIT param value: {split_param_value}")

    def is_ronin(self):
        return self.get_param_value(PrepParam.SPLIT) == 3

    def get_types_to_be_repr(self) -> List[Type]:
        res = []
        if self.get_param_value(PrepParam.SPLIT) in [1, 2, 4, 5, 6, 7, 8, 9]:
            res.extend([SplitContainer, Word])
        if self.get_param_value(PrepParam.SPLIT) in [2, 3, 4, 5, 6, 7, 8, 9]:
            res.append(Number)
        res.extend(com_str_to_types_to_be_repr[self.get_param_value(PrepParam.COM_STR)])
        res.extend(en_only_to_types_to_be_repr[self.get_param_value(PrepParam.EN_ONLY)])
        if self.get_param_value(PrepParam.TABS_NEWLINES):
            res.extend([NewLine, Tab])
        return res

    def get_repr_config(self, bpe_data: Optional[BpeData]):
        return ReprConfig(self.get_types_to_be_repr(),
                          bpe_data,
                          self.get_param_value(PrepParam.CAPS) == 1,
                          self.get_number_splitter(),
                          self.get_word_splitter(),
                          self.is_ronin())

    def is_bpe(self):
        """
        Check if this config corresponds to preprocessing with BPE.
        Note: splitting into chars is implemented as BPE with 0 merges, so in this case this method will also return True.

        :return: True if this config corresponds to preprocessing with BPE, False otherwise.
        """
        return self.get_param_value(PrepParam.SPLIT) in [4, 5, 6, 7, 8, 9]


com_str_to_types_to_be_repr = {
    0: [],
    1: [StringLiteral],
    2: [StringLiteral, OneLineComment, MultilineComment],
    3: [OneLineComment, MultilineComment]
}

en_only_to_types_to_be_repr = {
    0: [],
    3: [NonEng]
}
