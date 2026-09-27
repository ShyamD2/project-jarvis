"""
Native Windows Core Audio Controller for Project J.A.R.V.I.S. (Phase 3 Computer Control).
Uses Windows Core Audio IAudioEndpointVolume interface via comtypes for direct,
instant (<2ms), zero-SendKeys, zero-focus-stealing master volume & mute manipulation.
Falls back gracefully to virtual key events when COM endpoint is unavailable.
"""

from __future__ import annotations
import sys
import time
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisNativeAudio")

_volume_interface = None
_com_initialized = False


def _init_core_audio():
    """Initializes COM IAudioEndpointVolume interface for default multimedia render device."""
    global _volume_interface, _com_initialized
    if sys.platform != "win32":
        return None

    if _volume_interface is not None:
        return _volume_interface

    try:
        import ctypes
        from ctypes import POINTER, c_float
        import comtypes
        from comtypes import GUID, IUnknown, COMMETHOD, HRESULT, CoCreateInstance, CLSCTX_ALL

        if not _com_initialized:
            try:
                comtypes.CoInitialize()
            except Exception:
                pass
            _com_initialized = True

        class IAudioEndpointVolume(IUnknown):
            _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
            _methods_ = [
                COMMETHOD([], HRESULT, 'RegisterControlChangeNotify'),
                COMMETHOD([], HRESULT, 'UnregisterControlChangeNotify'),
                COMMETHOD([], HRESULT, 'GetChannelCount'),
                COMMETHOD([], HRESULT, 'SetMasterVolumeLevel'),
                COMMETHOD([], HRESULT, 'SetMasterVolumeLevelScalar',
                          (['in'], c_float, 'fLevel'),
                          (['in'], POINTER(GUID), 'pguidEventContext')),
                COMMETHOD([], HRESULT, 'GetMasterVolumeLevel'),
                COMMETHOD([], HRESULT, 'GetMasterVolumeLevelScalar',
                          (['out', 'retval'], POINTER(c_float), 'pfLevel')),
                COMMETHOD([], HRESULT, 'SetChannelVolumeLevel'),
                COMMETHOD([], HRESULT, 'SetChannelVolumeLevelScalar'),
                COMMETHOD([], HRESULT, 'GetChannelVolumeLevel'),
                COMMETHOD([], HRESULT, 'GetChannelVolumeLevelScalar'),
                COMMETHOD([], HRESULT, 'SetMute',
                          (['in'], ctypes.c_bool, 'bMute'),
                          (['in'], POINTER(GUID), 'pguidEventContext')),
                COMMETHOD([], HRESULT, 'GetMute',
                          (['out', 'retval'], POINTER(ctypes.c_bool), 'pbMute')),
            ]

        class IMMDevice(IUnknown):
            _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
            _methods_ = [
                COMMETHOD([], HRESULT, 'Activate',
                          (['in'], POINTER(GUID), 'iid'),
                          (['in'], ctypes.c_ulong, 'dwClsCtx'),
                          (['in'], POINTER(ctypes.c_int), 'pActivationParams'),
                          (['out', 'retval'], POINTER(POINTER(IUnknown)), 'ppInterface')),
            ]

        class IMMDeviceEnumerator(IUnknown):
            _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
            _methods_ = [
                COMMETHOD([], HRESULT, 'EnumAudioEndpoints'),
                COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint',
                          (['in'], ctypes.c_int, 'dataFlow'),
                          (['in'], ctypes.c_int, 'role'),
                          (['out', 'retval'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
            ]

        CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
        enumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
        endpoint = enumerator.GetDefaultAudioEndpoint(0, 1)  # eRender=0, eMultimedia=1
        endpoint_vol = endpoint.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        _volume_interface = ctypes.cast(endpoint_vol, POINTER(IAudioEndpointVolume))
        return _volume_interface
    except Exception as e:
        logger.debug(f"[NativeAudio] Core Audio COM init notice: {e}")
        return None


def get_master_volume() -> Optional[float]:
    """Returns current Windows master audio volume percentage (0.0 to 100.0)."""
    vol_iface = _init_core_audio()
    if vol_iface:
        try:
            scalar = vol_iface.GetMasterVolumeLevelScalar()
            return round(scalar * 100.0, 1)
        except Exception as e:
            logger.debug(f"[NativeAudio] Error reading volume scalar: {e}")
    return None


def set_master_volume(level_percent: float) -> bool:
    """
    Sets master audio volume directly in hardware endpoint in <2ms without stealing window focus.
    """
    vol_iface = _init_core_audio()
    clamped = max(0.0, min(100.0, float(level_percent)))
    scalar = clamped / 100.0

    if vol_iface:
        try:
            vol_iface.SetMasterVolumeLevelScalar(scalar, None)
            logger.info(f"🔊 [NativeAudio] Master volume set to {clamped:.1f}% via Core Audio endpoint.")
            return True
        except Exception as e:
            logger.warning(f"[NativeAudio] Core Audio SetMasterVolumeLevelScalar failed: {e}")

    # Fallback to keybd_event
    try:
        import ctypes
        user32 = ctypes.windll.user32
        curr = get_master_volume() or 50.0
        diff = int((clamped - curr) / 2.0)
        vk = 0xAF if diff > 0 else 0xAE
        for _ in range(abs(diff)):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(0.01)
        return True
    except Exception as e:
        logger.error(f"[NativeAudio] Volume adjustment fallback failed: {e}")
        return False


def get_mute() -> Optional[bool]:
    """Returns True if master audio is currently muted."""
    vol_iface = _init_core_audio()
    if vol_iface:
        try:
            return bool(vol_iface.GetMute())
        except Exception as e:
            logger.debug(f"[NativeAudio] Error reading mute state: {e}")
    return None


def set_mute(mute: bool) -> bool:
    """Sets master mute status directly."""
    vol_iface = _init_core_audio()
    if vol_iface:
        try:
            vol_iface.SetMute(bool(mute), None)
            logger.info(f"🔇 [NativeAudio] Audio mute state set to: {mute}")
            return True
        except Exception as e:
            logger.warning(f"[NativeAudio] Core Audio SetMute failed: {e}")

    # Fallback to toggle keybd_event
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(0xAD, 0, 0, 0)
        user32.keybd_event(0xAD, 0, 2, 0)
        return True
    except Exception:
        return False
