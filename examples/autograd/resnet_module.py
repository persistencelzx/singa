#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

# the code is modified from
# https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py

from singa import opt
from singa import device
from singa import tensor
from singa import module
from singa import autograd

import time
import numpy as np
from tqdm import trange


def conv3x3(in_planes, out_planes, stride=1):
    """3x3 convolution with padding"""
    return autograd.Conv2d(
        in_planes,
        out_planes,
        kernel_size=3,
        stride=stride,
        padding=1,
        bias=False,
    )


class BasicBlock(autograd.Layer):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = autograd.BatchNorm2d(planes)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = autograd.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def __call__(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = autograd.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out = autograd.add(out, residual)
        out = autograd.relu(out)

        return out


class Bottleneck(autograd.Layer):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = autograd.Conv2d(inplanes,
                                     planes,
                                     kernel_size=1,
                                     bias=False)
        self.bn1 = autograd.BatchNorm2d(planes)
        self.conv2 = autograd.Conv2d(planes,
                                     planes,
                                     kernel_size=3,
                                     stride=stride,
                                     padding=1,
                                     bias=False)
        self.bn2 = autograd.BatchNorm2d(planes)
        self.conv3 = autograd.Conv2d(planes,
                                     planes * self.expansion,
                                     kernel_size=1,
                                     bias=False)
        self.bn3 = autograd.BatchNorm2d(planes * self.expansion)

        self.downsample = downsample
        self.stride = stride

    def __call__(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = autograd.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = autograd.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out = autograd.add(out, residual)
        out = autograd.relu(out)

        return out


__all__ = [
    'ResNet', 'resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152'
]


class ResNet(module.Module):

    def __init__(self, block, layers, num_classes=1000):
        self.inplanes = 64
        super(ResNet, self).__init__()
        self.conv1 = autograd.Conv2d(3,
                                     64,
                                     kernel_size=7,
                                     stride=2,
                                     padding=3,
                                     bias=False)
        self.bn1 = autograd.BatchNorm2d(64)
        self.maxpool = autograd.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        self.avgpool = autograd.AvgPool2d(7, stride=1)
        self.fc = autograd.Linear(512 * block.expansion, num_classes)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            conv = autograd.Conv2d(
                self.inplanes,
                planes * block.expansion,
                kernel_size=1,
                stride=stride,
                bias=False,
            )
            bn = autograd.BatchNorm2d(planes * block.expansion)

            def _downsample(x):
                return bn(conv(x))

            downsample = _downsample

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        def forward(x):
            for layer in layers:
                x = layer(x)
            return x

        return forward

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = autograd.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = autograd.flatten(x)
        x = self.fc(x)

        return x

    def loss(self, out, ty):
        return autograd.softmax_cross_entropy(out, ty)

    def optim(self, loss):
        self.optimizer.backward_and_update(loss)

    def set_optimizer(self, optimizer):
        self.optimizer = optimizer


def resnet18(pretrained=False, **kwargs):
    """Constructs a ResNet-18 model.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(BasicBlock, [2, 2, 2, 2], **kwargs)

    return model


def resnet34(pretrained=False, **kwargs):
    """Constructs a ResNet-34 model.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(BasicBlock, [3, 4, 6, 3], **kwargs)

    return model


def resnet50(pretrained=False, **kwargs):
    """Constructs a ResNet-50 model.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 6, 3], **kwargs)

    return model


def resnet101(pretrained=False, **kwargs):
    """Constructs a ResNet-101 model.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 23, 3], **kwargs)

    return model


def resnet152(pretrained=False, **kwargs):
    """Constructs a ResNet-152 model.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 8, 36, 3], **kwargs)

    return model


def train_resnet(sgd,
                 niters,
                 batch_size,
                 DIST=True,
                 graph=True,
                 sequential=False):
    device_id = 0
    world_size = 1
    rank_in_global = 0
    IMG_SIZE = 224

    if DIST:
        sgd = opt.DistOpt(sgd)
        world_size = sgd.world_size
        device_id = sgd.rank_in_local
        rank_in_global = sgd.rank_in_global

    dev = device.create_cuda_gpu_on(device_id)

    tx = tensor.Tensor((batch_size, 3, IMG_SIZE, IMG_SIZE), dev)
    ty = tensor.Tensor((batch_size,), dev, tensor.int32)
    x = np.random.randn(batch_size, 3, IMG_SIZE, IMG_SIZE).astype(np.float32)
    y = np.random.randint(0, 1000, batch_size, dtype=np.int32)
    tx.copy_from_numpy(x)
    ty.copy_from_numpy(y)

    # construct the model
    model = resnet50()
    model.train()
    model.on_device(dev)
    model.set_optimizer(sgd)
    model.graph(graph, sequential)

    # train model
    dev.Sync()
    start = time.time()
    with trange(niters) as t:
        for _ in t:
            out = model(tx)
            loss = model.loss(out, ty)
            model.optim(loss)

    dev.Sync()
    end = time.time()
    titer = (end - start) / float(niters)
    throughput = float(niters * batch_size * world_size) / (end - start)
    if rank_in_global == 0:
        print("Throughput = {} per second".format(throughput), flush=True)
        print("TotalTime={}".format(end-start), flush=True)
        print("Total={}".format(titer), flush=True)


if __name__ == "__main__":

    DIST = True
    graph = True
    sequential = False
    niters = 100
    batch_size = 32

    sgd = opt.SGD(lr=0.1, momentum=0.9, weight_decay=1e-5)

    train_resnet(sgd=sgd,
                 niters=niters,
                 batch_size=batch_size,
                 DIST=DIST,
                 graph=graph,
                 sequential=sequential)
