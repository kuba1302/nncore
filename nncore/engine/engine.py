# Copyright (c) Ye Liu. Licensed under the MIT License.

from collections import OrderedDict

import torch
import wandb

import nncore
from nncore.nn import build_model
from nncore.optim import build_optimizer
from nncore.utils import CfgNode
from .buffer import Buffer
from .builder import build_dataloader, build_hook
from .comm import gather, is_distributed, is_main_process, sync
from .hooks import Hook
from .utils import get_checkpoint, load_checkpoint

_DEFAULT_STAGES = [
    dict(
        epochs=5,
        optimizer=dict(type='SGD', lr=1e-2, momentum=0.9, weight_decay=1e-4),
        lr_schedule=dict(type='iter', policy='cosine'),
        warmup=dict(type='iter', policy='linear', steps=500, ratio=0.001),
        validation=dict(interval=1))
]

_DEFAULT_HOOKS = [
    'TimerHook', 'LrUpdaterHook', 'OptimizerHook', 'CheckpointHook',
    'EvalHook', 'EventWriterHook'
]


@nncore.bind_getter('mode', 'max_stages', 'max_epochs', 'max_iters',
                    'start_iter', 'stage', 'epoch', 'iter', 'kwargs')
class Engine(object):
    """
    An engine that can take over the whole training, validation, and testing
    process, with all the baby-sitting works (stage control, optimizer
    configuration, lr scheduling, checkpoint management, metrics & tensorboard
    writing, etc.) done automatically.

    Args:
        model (:obj:`nn.Module` | cfg | str): The model or config of the model.
            The :obj:`forward` method of the model should return a dict
            containing a ``_avg_factor`` field indicating the number of
            samples in the current batch, and optionally a ``_out`` field
            denoting the model outputs to be collected and evaluated.
        data_loaders (dict | str): The configs of data loaders for training,
            validation, and testing. The dict should be in the format of
            ``dict(train=train_loader, val=val_loader, test=test_loader)``.
        stages (list[dict] | dict | None, optional): The stage config or list
            of stage configs to be scheduled. Each stage config should be a
            dict containing the following fields:

            - `epochs` (int): Number of epochs in the stage.
            - `optimizer` (:obj:`optim.Optimizer` | dict): The optimizer or \
                an optimizer config containing the following fields:

                - `type` (str): Type of the optimizer, which can be accessed \
                    via :obj:`torch.optim` attributes, e.g. ``'SGD'``.
                - `configs for the optimizer, e.g.` ``lr=0.01, momentum=0.9``.

            - `lr_schedule` (dict, optional): The learning rate schedule \
                config containing the following fields:

                - `type` (str): Type of the learning rate schedule. Expected \
                    values include ``'epoch'`` and ``'iter'``, indicating \
                    updating learning rates every epoch or iteration.
                - `policy` (str): The learning rate policy to use. Currently \
                    supported policies include ``step``, ``cosine``, ``exp``, \
                    ``poly``, and ``inv``.
                - `configs for the learning rate policy, e.g.` \
                    ``target_lr=0``. Please refer to :obj:`LrUpdaterHook` for \
                    full configs.

            - `warmup` (dict, optional): The warm-up policy config containing \
                the following fields:

                - `type` (str): Type of the warm-up schedule. Expected values \
                    include ``'epoch'`` and ``'iter'``, indicating warming up \
                    for ``step`` epochs for iterations.
                - `policy` (str): The warm-up policy to use. Currently \
                    supported policies include ``linear``, ``exp`` and \
                    ``constant``.
                - `step` (int): Number of iterations to warm-up.
                - `ratio` (float): The ratio of learning rate to start with. \
                    Expected values are in the range of ``0 ~ 1``.

            - `validation` (dict, optional): The validation config containing \
                the following fields:

                - `interval` (int, optional): The interval of performing \
                    validation. ``0`` means not performing validation. \
                    Default: ``0``.
                - `offset` (int, optional): The number of epochs to skip \
                    before counting the interval. Default: ``0``.

            Default: ``None``.
        hooks (list[:obj:`Hook` | dict | str] | None, optional): The list of
            extra hooks to be registered. Each hook can be represented as a
            :obj:`Hook`, a dict or a str. Default: ``None``.
        buffer_size (int, optional): Maximum size of the buffer. Default:
            ``100000``.
        logger (:obj:`logging.Logger` | str | None, optional): The logger or
            name of the logger to use. Default: ``None``.
        work_dir (str | None, optional): Path to the working directory. If not
            specified, the default working directory will be used. Default:
            ``None``.
        seed (int | None, optional): The random seed to use in data loaders.
            Default: ``None``.
        meta (any | None, optional): A dictionary-like object containing meta
            data of this engine. Default: ``None``.

    Example:
        >>> # Build model
        >>> model = build_model()
        ...
        >>> # Build data loaders
        >>> train_loader = build_dataloader(split='train')
        >>> val_loader = build_dataloader(split='val')
        >>> data_loaders = dict(train=train_loader, val=val_loader)
        ...
        >>> # Configure stages:
        >>> # [Stage 1] Train the model for 5 epochs using Adam optimizer with
        >>> # a fixed learning rate (1e-3) and a linear warm-up policy.
        >>> # [Stage 2] Train the model for another 3 epochs using SGD with
        >>> # momentum optimizer and an iter-based cosine learning rate
        >>> # schedule. Perform validation after every training epoch.
        >>> stages = [
        ...     dict(
        ...         epochs=5,
        ...         optimizer=dict(type='Adam', lr=1e-3),
        ...         warmup=dict(type='iter', policy='linear', steps=500)),
        ...     dict(
        ...         epochs=3,
        ...         optimizer=dict(type='SGD', lr=1e-3, momentum=0.9),
        ...         lr_schedule=dict(type='iter', policy='cosine'),
        ...         validation=dict(interval=1))
        ... ]
        ...
        >>> # Initialize and launch engine
        >>> engine = Engine(model, data_loaders, stages=stages)
        >>> engine.launch()
    """

    def __init__(self,
                 model,
                 data_loaders,
                 stages=None,
                 hooks=None,
                 buffer_size=100000,
                 logger=None,
                 work_dir=None,
                 seed=None,
                 meta=None,
                 **kwargs):
        self.model = build_model(model, **kwargs)
        wandb.watch(self.model)
        if 'train' not in data_loaders:
            data_loaders = dict(train=data_loaders)

        for a, b in (('val', 'test'), ('test', 'val')):
            if a not in data_loaders:
                loader = data_loaders[b if b in data_loaders else 'train']
                if isinstance(loader, dict):
                    data_loaders[a] = loader.copy()
                else:
                    data_loaders[a] = loader

        self.data_loaders = {
            k: build_dataloader(v, seed=seed)
            for k, v in data_loaders.items()
        }

        if isinstance(stages, dict):
            self.stages = [stages]
        else:
            self.stages = stages or _DEFAULT_STAGES

        self.register_hook(_DEFAULT_HOOKS)
        if is_distributed():
            self.register_hook('SamplerSeedHook', before='OptimizerHook')
        if hooks is not None:
            self.register_hook(hooks)

        time_str = nncore.get_timestamp()
        self.work_dir = work_dir or nncore.join('work_dirs', time_str)

        log_file = nncore.join(self.work_dir, time_str + '.log')
        self.logger = nncore.get_logger(logger, log_file=log_file)

        self.buffer = Buffer(max_size=buffer_size, logger=self.logger)
        self.reset_states()

        self.meta = meta

    @property
    def cur_stage(self):
        return self.stages[self._stage]

    @property
    def epoch_in_stage(self):
        cumsum = 0
        for stage in self.stages:
            if self._epoch + 1 <= cumsum + stage['epochs']:
                return self._epoch - cumsum
            cumsum += stage['epochs']
        return self.stages[-1]['epochs']

    @property
    def iter_in_stage(self):
        cumsum = 0
        for i in range(self._stage):
            cumsum += len(
                self.data_loaders['train']) * self.stages[i]['epochs']
        return self._iter - cumsum

    @property
    def iter_in_epoch(self):
        return self._iter - len(self.data_loaders['train']) * self._epoch

    def _call_hook(self, name):
        for hook in self.hooks.values():
            getattr(hook, name)(self)

    def reset_states(self):
        self.buffer.clear()
        self._max_stages = 0 if self.stages is None else len(self.stages)
        self._max_epochs = 0 if self.stages is None else sum(
            stage['epochs'] for stage in self.stages)
        self._max_iters = (len(self.data_loaders['train']) if 'train'
                           in self.data_loaders else 0) * self._max_epochs
        self._start_iter = self._stage = self._epoch = self._iter = 0

    def register_hook(self, hook, before=None, overwrite=True, **kwargs):
        """
        Register a hook or a list of hooks into the engine.

        Args:
            hook (list | :obj:`Hook` | dict | str): The hook or list of hooks
                to be registered. Each hook can be represented as a
                :obj:`Hook`, a dict or a str.
            before (str, optional): Name of the hook to be inserted before. If
                not specified, the new hook will be added to the end of hook
                list. Default: ``None``.
            overwrite (bool, optional): Whether to overwrite the old hook with
                the same name if exists. Default: ``True``.
        """
        if isinstance(hook, (list, tuple)):
            for h in hook:
                self.register_hook(
                    h, before=before, overwrite=overwrite, **kwargs)
            return
        elif isinstance(hook, (dict, str)):
            hook = build_hook(hook, **kwargs)
        elif not isinstance(hook, Hook):
            raise TypeError(
                "hook must be a Hook, a dict or a str, but got '{}'".format(
                    type(hook)))

        if not hasattr(self, 'hooks'):
            self.hooks = OrderedDict()

        if hook.name in self.hooks:
            if overwrite:
                keys = list(self.hooks.keys())
                if before is None and keys[-1] != hook.name:
                    before = keys[keys.index(hook.name) + 1]
                self.hooks.pop(hook.name)
            else:
                raise KeyError("hook '{}' exists".format(hook.name))

        self.hooks[hook.name] = hook

        if before is not None:
            if before not in self.hooks:
                raise ValueError("hook '{}' not found".format(before))

            keys = list(self.hooks.keys())
            for key in keys[keys.index(before):-1]:
                self.hooks.move_to_end(key)

    def unregister_hook(self, hook):
        """
        Unregister a hook or a list of hooks from the engine.

        Args:
            hook (list | :obj:`Hook` | str): The hook or list of hooks to be
                unregistered. Each hook can be represented as a :obj:`Hook` or
                a str.
        """
        if isinstance(hook, (list, tuple)):
            for h in hook:
                self.unregister_hook(h)
            return

        if isinstance(hook, Hook):
            hook = hook.name
        self.hooks.pop(hook)

    def load_checkpoint(self, checkpoint, **kwargs):
        """
        Load checkpoint from a file or an URL.

        Args:
            checkpoint (dict | str): A dict, a filename, an URL or a
                ``torchvision://<model_name>`` str indicating the checkpoint.
        """
        load_checkpoint(
            self.model,
            checkpoint,
            map_location=next(self.model.parameters()).device,
            logger=self.logger,
            **kwargs)

        if isinstance(checkpoint, str):
            self.logger.info('Loaded checkpoint from {}'.format(checkpoint))
        else:
            self.logger.info('Loaded checkpoint')

    def resume(self, checkpoint, **kwargs):
        """
        Resume from a checkpoint file.

        Args:
            checkpoint (dict | str): A dict, a filename or an URL indicatin
                the checkpoint.
        """
        if isinstance(checkpoint, str):
            checkpoint = get_checkpoint(
                checkpoint, map_location=next(self.model.parameters()).device)

        if self.stages != checkpoint['meta']['stages']:
            self.logger.warn(
                'Stages in the engine and checkpoint are mismatch:'
                '\n\nCurrent stages: {}\n\nCheckpoint stages: {}'.format([
                    c.to_dict() if isinstance(c, CfgNode) else c
                    for c in self.stages
                ], checkpoint['meta']['stages']))

        load_checkpoint(self.model, checkpoint, logger=self.logger, **kwargs)

        self._epoch = checkpoint['meta']['epoch']
        self._iter = self._start_iter = checkpoint['meta']['iter']

        cumsum, count = 0, 0
        for stage in self.stages:
            if self._epoch + 1 <= cumsum + stage['epochs']:
                break
            count += 1
        self._stage = count

        if 'optimizer' in checkpoint:
            self.optimizer = build_optimizer(
                self.cur_stage['optimizer'], params=self.model.parameters())
            self.optimizer.load_state_dict(checkpoint['optimizer'])
        else:
            raise KeyError('optimizer not found in the checkpoint')

        self.logger.info('Resumed stage {}, epoch {}, iter {}'.format(
            self._stage + 1, self._epoch, self._iter))
    
    def log_output(self, output, output_type: str):
        wandb.log({f"{output_type}_{k}": v for k, v in output.items()})
        
    def train_iter(self, data):
        self._call_hook('before_train_iter')

        output = self.model(data, mode=self._mode, **self._kwargs)

        self.losses = {k: v for k, v in output.items() if 'loss' in k}
        if 'loss' not in output:
            self.losses['loss'] = output['loss'] = sum(
                v for v in self.losses.values())

        for key, value in output.items():
            self.buffer.update(
                key,
                value.detach().cpu() if torch.is_tensor(value) else value)
        self.log_output(output, "train")
        self._call_hook('after_train_iter')
        self._iter += 1

    def val_iter(self, data):
        self._call_hook('before_val_iter')

        with torch.no_grad():
            output = self.model(data, mode=self._mode, **self._kwargs)

        if any('loss' in key for key in output) and 'loss' not in output:
            output['loss'] = sum(v for k, v in output.items() if 'loss' in k)

        for key, value in output.items():
            self.buffer.update(
                key,
                value.detach().cpu() if torch.is_tensor(value) else value)
        self.log_output(output, "valid")
        self._call_hook('after_val_iter')

    def test_iter(self, data):
        with torch.no_grad():
            output = self.model(data, mode=self._mode, **self._kwargs)

        for key, value in output.items():
            self.buffer.update(
                key,
                value.detach().cpu() if torch.is_tensor(value) else value)

    def train_epoch(self):
        self._mode = 'train'
        self.model.train()
        self.data_loader = self.data_loaders[self._mode]

        if callable(getattr(self.data_loader.dataset, 'set_state', None)):
            self.data_loader.dataset.set_state(self._mode)

        self._call_hook('before_train_epoch')

        for data in self.data_loader:
            self.train_iter(data)

        self._call_hook('after_train_epoch')
        self._epoch += 1

    def val_epoch(self):
        self.logger.info('Validating...')
        self._mode = 'val'
        self.model.eval()
        self.buffer.pop('_out', None)
        self.data_loader = self.data_loaders[self._mode]

        if callable(getattr(self.data_loader.dataset, 'set_state', None)):
            self.data_loader.dataset.set_state(self._mode)

        self._call_hook('before_val_epoch')

        prog_bar = nncore.ProgressBar(len(self.data_loader))
        for data in self.data_loader:
            self.val_iter(data)
            prog_bar.update()

        self._call_hook('after_val_epoch')

    def test_epoch(self):
        self.logger.info('Evaluating...')
        self._mode = 'test'
        self.model.eval()
        self.buffer.pop('_out', None)
        self.data_loader = self.data_loaders[self._mode]

        if callable(getattr(self.data_loader.dataset, 'set_state', None)):
            self.data_loader.dataset.set_state(self._mode)

        prog_bar = nncore.ProgressBar(len(self.data_loader))
        for data in self.data_loader:
            self.test_iter(data)
            prog_bar.update()

    def run_stage(self):
        if isinstance(self.cur_stage['optimizer'], dict):
            optim = self.cur_stage['optimizer'].copy()
            optim_type = optim.pop('type')
            optim_args = ['{}: {}'.format(k, v) for k, v in optim.items()]
            optim = '{}({})'.format(optim_type, ', '.join(optim_args))
        else:
            optim = '{}()'.format(
                self.cur_stage['optimizer'].__class__.__name__)

        self.logger.info('Stage: {}, epochs: {}, optimizer: {}'.format(
            self._stage + 1, self.cur_stage['epochs'], optim))

        if self.epoch_in_stage == 0:
            self.optimizer = build_optimizer(
                self.cur_stage['optimizer'], params=self.model.parameters())
            
        wandb.config.update({"optimizer": optim_type})
        self._call_hook('before_stage')

        for _ in range(self.cur_stage['epochs'] - self.epoch_in_stage):
            self.train_epoch()
            cfg = self.cur_stage.get('validation')
            if (cfg is not None and 'val' in self.data_loaders
                    and cfg.get('interval', 0) > 0
                    and self.epoch_in_stage > cfg.get('offset', 0)
                    and self.epoch_in_stage % cfg.get('interval', 0) == 0):
                self.val_epoch()

        self._call_hook('after_stage')
        self._stage += 1

    def evaluate(self):
        """
        Perform evaluation. This methods is expected to be called after
        validation or testing.
        """
        blob = self.buffer.pop('_out')
        blob = gather(blob)

        if is_main_process():
            blob = nncore.concat(blob)

            cfg = self.cur_stage.get('validation')
            if cfg is not None:
                cfg = cfg.copy()
                cfg.pop('interval', None)
                cfg.pop('offset', None)
            else:
                cfg = dict()

            output = self.data_loader.dataset.evaluate(
                blob, logger=self.logger, **cfg)
            self.log_output(output, "eval")
        else:
            output = dict()

        sync()
        return output

    def launch(self, eval=False, **kwargs):
        """
        Launch the engine.

        Args:
            eval (bool, optional): Whether to run evaluation only. Default:
                ``False``.
        """
        self._kwargs = kwargs

        if eval:
            self.test_epoch()
            output = self.evaluate()
            self.logger.info(
                'Evaluation results: ' +
                ', '.join(['{}: {}'.format(k, v) for k, v in output.items()]))
            return output

        self.logger.info('Launch engine, host: {}, work_dir: {}'.format(
            nncore.get_host_info(), self.work_dir))
        self._call_hook('before_launch')

        while self._stage < self._max_stages:
            self.run_stage()

        self._call_hook('after_launch')

        self.log_model_as_artifact()
        
    def log_model_as_artifact(self, model_name="umt-model", artifact_name="umt-model"):
        """
        Log the model as a wandb artifact.
        
        Args:
            model_name (str): Name for the saved model file.
            artifact_name (str): Name for the wandb artifact.
        """
        # Save the model to a file
        model_path = f"{self.work_dir}/{model_name}.pth"
        torch.save(self.model.state_dict(), model_path)
        
        # Create a wandb artifact and log it
        artifact = wandb.Artifact(
            name=artifact_name,
            type="model",
            description="Trained model weights",
            metadata=dict(epoch=self._epoch)
        )
        artifact.add_file(model_path)
        wandb.log_artifact(artifact)
