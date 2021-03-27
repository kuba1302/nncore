<div align="center">

![Logo](https://raw.githubusercontent.com/yeliudev/nncore/main/.github/nncore-logo.svg)

# NNCore

**A lightweight PyTorch code wrapper for ML researchers.**

[![PyPI](https://badgen.net/pypi/v/nncore?label=PyPI&icon=pypi)](https://pypi.org/project/nncore)
[![License](https://badgen.net/github/license/yeliudev/nncore?label=License)](https://github.com/yeliudev/nncore/blob/main/LICENSE)
[![Coveralls](https://badgen.net/coveralls/c/github/yeliudev/nncore/main?label=Coverage)](https://coveralls.io/github/yeliudev/nncore?branch=main)
[![Gitter](https://badgen.net/badge/Chat/on%20gitter/cyan?icon=gitter)](https://gitter.im/nncore-dev/community?utm_source=share-link&utm_medium=link&utm_campaign=share-link)
[![Codacy](https://badgen.net/codacy/grade/c55266f7dc904b5d8c31b15bafb1117c?label=Code%20Quality&icon=codacy)](https://www.codacy.com/gh/yeliudev/nncore/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=yeliudev/nncore&amp;utm_campaign=Badge_Grade)

</div>

NNCore is a library that provides common functionalities for Machine Learning and Deep Learning researchers. This project aims at helping users focus more on science but not engineering during researches. The essential functionalities include but are not limited to:

- Universal I/O APIs
- Efficient implementations of layers and losses that are not included in PyTorch
- Extended methods for distributed training
- More powerful data loading techniques
- An engine that can take over the whole training and testing process, with all the baby-sitting works (stage control, optimizer configuration, lr scheduling, checkpoint management, metrics & tensorboard writing, etc.) done automatically. See an [example](https://github.com/yeliudev/nncore/blob/main/examples/mnist.py) for details.

Note that some methods in the library work with PyTorch 1.6+, but the installation of PyTorch is not necessary.

## Continuous Integration

| Platform / Python Version | 3.6 | 3.7 | 3.8 | 3.9 |
| :-: | :-: | :-: | :-: | :-: |
| Ubuntu 16.04 | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/0?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/1?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/2?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/3?icon=github)][link] |
| Ubuntu 18.04 | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/4?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/5?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/6?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/7?icon=github)][link] |
| Ubuntu 20.04 | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/8?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/9?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/10?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/11?icon=github)][link] |
| macOS 10.15 | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/12?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/13?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/14?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/15?icon=github)][link] |
| Windows | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/16?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/17?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/18?icon=github)][link] | [![Build](https://badgen.net/runkit/yeliudev/nncore-badge/19?icon=github)][link] |

## Installation

You may install nncore directly from PyPI

```
pip install nncore
```

or manually from source

```
git clone https://github.com/yeliudev/nncore.git
cd nncore
pip install -e .
```

## Getting Started

Please refer to our [documentation](https://nncore.readthedocs.io/) for how to incorperate nncore into your projects.

## Acknowledgements

This library is licensed under the [MIT License](https://github.com/yeliudev/nncore/blob/main/LICENSE). Part of the code in this project is modified from [mmcv](https://github.com/open-mmlab/mmcv) and [fvcore](https://github.com/facebookresearch/fvcore) with many thanks to the original authors.

[link]: https://github.com/yeliudev/nncore/actions/workflows/build.yml
