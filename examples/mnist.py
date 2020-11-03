# Copyright (c) Ye Liu. All rights reserved.

import torch
import torch.nn as nn
import torchvision
from torch.utils.data import DataLoader
from torchvision.datasets import MNIST

import nncore
from nncore.engine import Engine

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class LeNet(nn.Module):

    def __init__(self):
        super(LeNet, self).__init__()

        # yapf:disable
        self.convs = nn.Sequential(
            nn.Conv2d(1, 6, 5, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, stride=2),
            nn.Conv2d(6, 16, 5, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, stride=2))
        self.fcs = nn.Sequential(
            nn.Linear(16 * 5 * 5, 120),
            nn.ReLU(inplace=True),
            nn.Linear(120, 84),
            nn.ReLU(inplace=True),
            nn.Linear(84, 10))
        # yapf:enable

        self.criterion = nn.CrossEntropyLoss()

    def forward(self, data, **kwargs):
        x, labels = data[0].to(device), data[1].to(device)
        x = self.convs(x)
        x = x.view(labels.numel(), -1)
        x = self.fcs(x)

        _, pred = torch.max(x, dim=1)
        acc = torch.eq(pred, labels).sum().float() / labels.numel()
        loss = self.criterion(x, labels)

        return dict(_num_samples=labels.numel(), acc=acc, loss=loss)


def main():
    # Load config from file
    cfg = nncore.Config.from_file('examples/config.py')
    cfg.freeze()

    # Prepare dataset and model
    transform = torchvision.transforms.Compose([
        torchvision.transforms.ToTensor(),
        torchvision.transforms.Normalize([0.5], [0.5])
    ])

    train = MNIST('data', train=True, transform=transform, download=True)
    train_loader = DataLoader(train, batch_size=16, shuffle=True)

    val = MNIST('data', train=False, transform=transform, download=True)
    val_loader = DataLoader(val, batch_size=64, shuffle=False)

    data_loaders = dict(train=train_loader, val=val_loader)
    model = LeNet().to(device)

    # Initialize and launch engine
    engine = Engine(model, data_loaders, **cfg)
    engine.launch()


if __name__ == '__main__':
    main()
