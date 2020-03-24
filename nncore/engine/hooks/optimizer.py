# Copyright (c) Ye Liu. All rights reserved.

from collections import OrderedDict

import torch.distributed as dist
from torch._utils import (_flatten_dense_tensors, _take_tensors,
                          _unflatten_dense_tensors)
from torch.nn.utils import clip_grad

from .base import HOOKS, Hook


def _allreduce_coalesced(tensors, world_size, bucket_size_mb):
    if bucket_size_mb > 0:
        bucket_size_bytes = bucket_size_mb * 1024 * 1024
        buckets = _take_tensors(tensors, bucket_size_bytes)
    else:
        buckets = OrderedDict()
        for tensor in tensors:
            tp = tensor.type()
            if tp not in buckets:
                buckets[tp] = []
            buckets[tp].append(tensor)
        buckets = buckets.values()

    for bucket in buckets:
        flat_tensors = _flatten_dense_tensors(bucket)
        dist.all_reduce(flat_tensors)
        flat_tensors.div_(world_size)
        for tensor, synced in zip(
                bucket, _unflatten_dense_tensors(flat_tensors, bucket)):
            tensor.copy_(synced)


def _allreduce_grads(params, coalesce, bucket_size_mb):
    grads = [
        param.grad.data for param in params
        if param.requires_grad and param.grad is not None
    ]
    world_size = dist.get_world_size()
    if coalesce:
        _allreduce_coalesced(grads, world_size, bucket_size_mb)
    else:
        for tensor in grads:
            dist.all_reduce(tensor.div_(world_size))


@HOOKS.register
class OptimizerHook(Hook):

    def clip_grads(self, params, cfg):
        clip_grad.clip_grad_norm_(
            filter(lambda p: p.requires_grad, params), **cfg)

    def after_train_iter(self, engine):
        engine.optimizer.zero_grad()
        loss = engine.cur_stage.get('loss', 'loss')
        engine.losses[loss].backward()
        grad_clip = engine.cur_stage.get('grad_clip', None)
        if grad_clip is not None:
            self.clip_grads(engine.model.parameters(), grad_clip)
        engine.optimizer.step()


@HOOKS.register
class DistOptimizerHook(OptimizerHook):

    def __init__(self, coalesce=True, bucket_size_mb=-1):
        super(DistOptimizerHook, self).__init__()
        self._coalesce = coalesce
        self._bucket_size_mb = bucket_size_mb

    def after_train_iter(self, engine):
        engine.optimizer.zero_grad()
        loss = engine.cur_stage.get('loss', 'loss')
        engine.losses[loss].backward()
        _allreduce_grads(engine.model.parameters(), self._coalesce,
                         self._bucket_size_mb)
        grad_clip = engine.cur_stage.get('grad_clip', None)
        if grad_clip is not None:
            self.clip_grads(engine.model.parameters(), grad_clip)
        engine.optimizer.step()
