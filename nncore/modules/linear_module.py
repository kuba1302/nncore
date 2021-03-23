# Copyright (c) Ye Liu. All rights reserved.

import torch.nn as nn

from .bricks import build_act_layer, build_norm_layer


class LinearModule(nn.Module):
    """
    A module that bundles linear/norm/activation layers.

    Args:
        in_features (int): number of input features
        out_features (int): number of output features
        bias (str or bool, optional): whether to add the bias term in the
            linear layer. If bias=`auto`, the module will decide it
            automatically base on whether it has a norm layer.
        norm_cfg (dict, optional): the config of norm layer
        act_cfg (dict, optional): the config of activation layer
        order (tuple[str], optional): the order of linear/norm/activation
            layers. It is expected to be a sequence of `msg_pass`, `norm` and
            `act`.
    """

    def __init__(self,
                 in_features,
                 out_features,
                 bias='auto',
                 norm_cfg=dict(type='BN1d'),
                 act_cfg=dict(type='ReLU', inplace=True),
                 order=('linear', 'norm', 'act')):
        super(LinearModule, self).__init__()
        self.with_norm = 'norm' in order and norm_cfg is not None
        self.with_act = 'act' in order and act_cfg is not None
        self.order = order

        self.linear = nn.Linear(
            in_features,
            out_features,
            bias=bias if bias != 'auto' else not self.with_norm)

        if self.with_norm:
            _norm_cfg = norm_cfg.copy()
            if _norm_cfg['type'] not in ('GN', 'LN'):
                _norm_cfg.setdefault('num_features', out_features)
            self.norm = build_norm_layer(_norm_cfg)

        if self.with_act:
            self.act = build_act_layer(act_cfg)

    def forward(self, x):
        for layer in self.order:
            if layer == 'linear':
                x = self.linear(x)
            elif layer == 'norm' and self.with_norm:
                x = self.norm(x)
            elif layer == 'act' and self.with_act:
                x = self.act(x)
        return x


def build_mlp(dims, with_last_act=False, **kwargs):
    """
    Build a multi-layer perceptron (MLP).

    Args:
        dims (list[int]): the sequence of numbers of dimensions of features
        with_last_act (bool, optional): whether to add an activation layer
            after the last linear layer

    Returns:
        layers (:obj:`nn.Sequential`): the constructed MLP module
    """
    _kwargs = kwargs.copy()
    layers = []

    for i in range(len(dims) - 1):
        if not with_last_act and i == len(dims) - 2:
            _kwargs['order'] = ('linear', )

        module = LinearModule(dims[i], dims[i + 1], **_kwargs)
        layers.append(module)

    return nn.Sequential(*layers)
