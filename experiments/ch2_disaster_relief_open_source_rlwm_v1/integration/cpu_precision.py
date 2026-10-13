"""Explicit CPU float32 execution overlay; upstream source stays unmodified."""
import torch
from .dreamer_relief import R2Dreamer, ReliefDreamer


class CPUFloat32CalGradMixin:
    def _cal_grad(self, *args, **kwargs):
        if self.device.type != 'cpu':
            return super()._cal_grad(*args, **kwargs)
        with torch.amp.autocast(device_type='cpu', enabled=False):
            return super()._cal_grad(*args, **kwargs)


class CPUFloat32Dreamer(CPUFloat32CalGradMixin, R2Dreamer):
    pass


class CPUFloat32ReliefDreamer(CPUFloat32CalGradMixin, ReliefDreamer):
    def checkpoint_metadata(self, observation):
        metadata = super().checkpoint_metadata(observation)
        metadata['cpu_precision'] = 'float32_overlay'
        return metadata
