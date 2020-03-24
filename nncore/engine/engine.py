# Copyright (c) Ye Liu. All rights reserved.

from collections import OrderedDict

import torch

import nncore
from .buffer import Buffer
from .hooks import HOOKS, Hook
from .utils import get_checkpoint, load_checkpoint


@nncore.bind_getter('hooks', 'max_stages', 'max_epochs', 'max_iters',
                    'start_iter', 'stage', 'epoch', 'iter')
class Engine(object):

    def __init__(self,
                 model,
                 data_loaders,
                 stages,
                 buffer_size=990125,
                 hooks=None,
                 logger=None,
                 work_dir=None):
        self.model = model
        self.data_loaders = data_loaders
        self.stages = stages
        self.work_dir = work_dir

        if work_dir is not None:
            nncore.mkdir(work_dir)

        self._hooks = OrderedDict()
        if hooks is not None:
            for hook in hooks:
                self.register_hook(hook)

        self.buffer = Buffer(max_size=buffer_size)
        self.logger = logger or nncore.get_logger()
        self.flush_states()

    @property
    def cur_stage(self):
        return self.stages[self._stage]

    @property
    def epoch_in_stage(self):
        cumsum = 0
        for stage in self.stages:
            if self._epoch + 1 <= cumsum + stage.epochs:
                return self._epoch - cumsum
            cumsum += stage.epochs
        return self.stages[-1].epochs

    @property
    def iter_in_stage(self):
        cumsum = 0
        for i in range(self._stage):
            cumsum += len(self.data_loaders['train']) * self.stages[i].epochs
        return self._iter - cumsum

    @property
    def iter_in_epoch(self):
        return self._iter - len(self.data_loaders['train']) * self._epoch

    def flush_states(self):
        self._max_stages = len(self.stages)
        self._max_epochs = sum(stage.epochs for stage in self.stages)
        self._max_iters = len(self.data_loaders['train']) * self._max_epochs
        self._start_iter = 0
        self._stage = 0
        self._epoch = 0
        self._iter = 0

    def _call_hook(self, name):
        for hook in self._hooks.values():
            getattr(hook, name)(self)

    def register_hook(self, hook, before=None):
        """
        Register a hook into the engine.

        Args:
            hook (:obj:`Hook` or dict): the hook to be registered
            before (str, optional): name of the hook to be inserted before. The
                new hook will be inserted into the end of the hook list by
                default.
        """
        if isinstance(hook, dict):
            hook = nncore.build_object(hook, HOOKS)
        elif not isinstance(hook, Hook):
            raise TypeError('hook must be a Hook or dict, but got {}'.format(
                type(hook)))

        if hook.name in self._hooks:
            raise ValueError("hook '{}' exists".format(hook.name))

        self._hooks[hook.name] = hook

        if before is not None:
            if before not in self._hooks:
                raise ValueError("hook '{}' not found".format(before))

            keys = list(self._hooks.keys())
            idx = keys.index(before)
            for key in keys[idx:-1]:
                self._hooks[key].move_to_end()

    def build_optimizer(self, optimizer):
        """
        Build an optimizer for the engine.

        Args:
            optimizer (any): an optimizer object or a dict used for
                constructing the optimizer
        """
        if isinstance(optimizer, dict):
            self.optimizer = nncore.build_object(
                optimizer, torch.optim, dict(params=self.model.parameters()))
        elif hasattr(optimizer, 'zero_grad') and hasattr(optimizer, 'step'):
            self.optimizer = optimizer
        else:
            raise TypeError("invalid optimizer: {}".format(optimizer))

    def load_checkpoint(self, checkpoint, strict=False):
        load_checkpoint(
            self.model,
            checkpoint,
            map_location=next(self.model.parameters()).device,
            strict=strict,
            logger=self.logger)

        if isinstance(checkpoint, str):
            self.logger.info('Loaded checkpoint from {}'.format(checkpoint))
        else:
            self.logger.info('Loaded checkpoint')

    def resume(self, checkpoint, with_optimizer=True, strict=False):
        if isinstance(checkpoint, str):
            checkpoint = get_checkpoint(
                checkpoint, map_location=next(self.model.parameters()).device)

        if self.stages != checkpoint['meta']['stages']:
            self.logger.warn(
                'Stages in the engine and checkpoint are mismatch')

        load_checkpoint(
            self.model, checkpoint, strict=strict, logger=self.logger)

        self._epoch = checkpoint['meta']['epoch']
        self._iter = self._start_iter = checkpoint['meta']['iter']

        cumsum, count = 0, 0
        for stage in self.stages:
            if self._epoch + 1 <= cumsum + stage.epochs:
                break
            count += 1
        self._stage = count

        if with_optimizer:
            if 'optimizer' in checkpoint:
                self.build_optimizer(self.cur_stage.optimizer)
                self.optimizer.load_state_dict(checkpoint['optimizer'])
                self._res_optim = True
            else:
                self.logger.warn('Optimizer not found in the checkpoint')

        self.logger.info('Resumed stage {}, epoch {}, iter {}'.format(
            self._stage + 1, self._epoch, self._iter))

    def train_iter(self, data):
        self._call_hook('before_train_iter')

        output = self.model(data, return_loss=True)

        self.losses = {k: v for k, v in output.items() if 'loss' in k}
        self.losses['loss'] = sum(v for v in self.losses.values())

        for key in output:
            self.buffer.update(key, output[key])

        self._call_hook('after_train_iter')
        self._iter += 1

    def val_iter(self, data):
        self._call_hook('before_val_iter')

        with torch.no_grad():
            output = self.model(data, return_loss=True)

        for key in output:
            self.buffer.update(key, output[key])

        self._call_hook('after_val_iter')

    def train_epoch(self):
        self.mode = 'train'
        self.model.train()
        self.data_loader = self.data_loaders['train']
        self._call_hook('before_train_epoch')

        for data in self.data_loader:
            self.train_iter(data)

        self._call_hook('after_train_epoch')
        self._epoch += 1

    def val_epoch(self):
        self.logger.info('Validating...')

        self.mode = 'val'
        self.model.eval()
        self.data_loader = self.data_loaders['val']
        self._call_hook('before_val_epoch')

        prog_bar = nncore.ProgressBar(len(self.data_loader))
        for data in self.data_loader:
            self.val_iter(data)
            prog_bar.update()

        self._call_hook('after_val_epoch')

    def run_stage(self):
        if isinstance(self.cur_stage.optimizer, dict):
            optim = self.cur_stage.optimizer.copy()
            optim_type = optim.pop('type')
            optim_args = ['{}: {}'.format(k, v) for k, v in optim.items()]
            optim = '{}({})'.format(optim_type, ', '.join(optim_args))
        else:
            optim = '{}()'.format(self.cur_stage.optimizer.__class__.__name__)

        self.logger.info('Stage: {}, epochs: {}, optimizer: {}'.format(
            self._stage + 1, self.cur_stage.epochs, optim))

        if self.epoch_in_stage == 0 and not getattr(self, '_res_optim', False):
            self.build_optimizer(self.cur_stage.optimizer)

        self._call_hook('before_stage')

        interval = self.cur_stage.get('val_interval', 0)
        while self.epoch_in_stage < self.cur_stage.epochs:
            self.train_epoch()
            if interval > 0 and self.epoch_in_stage % interval == 0:
                self.val_epoch()

        self._call_hook('after_stage')
        self._stage += 1

    def launch(self):
        self.logger.info('Start running, host: {}, work_dir: {}'.format(
            nncore.get_host_info(), self.work_dir))
        self._call_hook('before_launch')

        while self._stage < self._max_stages:
            self.run_stage()

        self._call_hook('after_launch')
