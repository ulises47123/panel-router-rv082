"""Ícono en la bandeja de Windows (junto al reloj) con menú "Abrir panel" / "Cerrar todo".

Solo usa ctypes (API de Windows), sin librerías extra, y funciona igual en 32 y
64 bits: todos los tipos que llevan punteros (WPARAM, LPARAM, LRESULT, HWND...)
se declaran con el tamaño correcto y se fijan argtypes/restype de cada función.
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HICON = wintypes.HANDLE
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

WM_NULL, WM_DESTROY, WM_CLOSE, WM_COMMAND = 0x0000, 0x0002, 0x0010, 0x0111
WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_LBUTTONUP = 0x0203, 0x0205, 0x0202
WM_APP = 0x8000
WM_BANDEJA = WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO, NIIF_USER, NIIF_LARGE_ICON = 0x1, 0x4, 0x20
MF_STRING, MF_SEPARATOR, MF_GRAYED = 0x0, 0x800, 0x1
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY, TPM_BOTTOMALIGN = 0x2, 0x100, 0x80, 0x20
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
IDI_APPLICATION = 32512
CMD_ABRIR, CMD_CERRAR = 1001, 1002


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID), ("hBalloonIcon", HICON)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", HICON)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _firmas():
    f = user32
    f.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]; f.DefWindowProcW.restype = LRESULT
    f.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]; f.RegisterClassExW.restype = wintypes.ATOM
    f.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                  wintypes.HINSTANCE, wintypes.LPVOID]
    f.CreateWindowExW.restype = wintypes.HWND
    f.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]; f.GetMessageW.restype = wintypes.BOOL
    f.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    f.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]; f.DispatchMessageW.restype = LRESULT
    f.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]; f.PostMessageW.restype = wintypes.BOOL
    f.PostQuitMessage.argtypes = [ctypes.c_int]
    f.DestroyWindow.argtypes = [wintypes.HWND]
    f.CreatePopupMenu.restype = wintypes.HMENU
    f.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    f.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    f.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 wintypes.HWND, wintypes.LPVOID]
    f.TrackPopupMenu.restype = wintypes.BOOL
    f.DestroyMenu.argtypes = [wintypes.HMENU]
    f.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    f.SetForegroundWindow.argtypes = [wintypes.HWND]
    f.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    f.LoadImageW.restype = wintypes.HANDLE
    f.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]; f.LoadIconW.restype = HICON
    f.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]; f.RegisterWindowMessageW.restype = wintypes.UINT
    f.DestroyIcon.argtypes = [HICON]
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]; kernel32.GetModuleHandleW.restype = wintypes.HMODULE


_firmas()


class Bandeja:
    def __init__(self, titulo: str, ruta_icono: str | None, al_abrir, al_cerrar, aviso: str | None = None):
        self.titulo = titulo[:127]
        self.ruta_icono = ruta_icono
        self.al_abrir = al_abrir
        self.al_cerrar = al_cerrar
        self.aviso = aviso
        self.hwnd = None
        self.hicon = None
        self._listo = threading.Event()
        self._proc = WNDPROC(self._wndproc)  # guardar la referencia (si no, el GC la borra)
        self._msg_taskbar = 0

    # --- ciclo de vida ------------------------------------------------------
    def iniciar(self) -> None:
        threading.Thread(target=self._bucle, name="bandeja", daemon=True).start()
        self._listo.wait(5)

    def cerrar(self) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def _bucle(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        clase = "PanelRouterBandeja"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = clase
        user32.RegisterClassExW(ctypes.byref(wc))
        # ventana invisible que recibe los clics del ícono
        self.hwnd = user32.CreateWindowExW(0, clase, self.titulo, 0, 0, 0, 0, 0, None, None, hinst, None)
        self._msg_taskbar = user32.RegisterWindowMessageW("TaskbarCreated")  # si se reinicia el Explorador
        if self.ruta_icono:
            self.hicon = user32.LoadImageW(None, self.ruta_icono, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not self.hicon:
            self.hicon = user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
        self._agregar_icono(con_aviso=True)
        self._listo.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _datos(self) -> NOTIFYICONDATAW:
        d = NOTIFYICONDATAW()
        d.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        d.hWnd = self.hwnd
        d.uID = 1
        return d

    def _agregar_icono(self, con_aviso=False) -> None:
        d = self._datos()
        d.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        d.uCallbackMessage = WM_BANDEJA
        d.hIcon = self.hicon
        d.szTip = self.titulo
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(d))
        if con_aviso and self.aviso:
            self.mostrar_aviso(self.titulo, self.aviso)

    def mostrar_aviso(self, titulo: str, texto: str) -> None:
        d = self._datos()
        d.uFlags = NIF_INFO
        d.szInfoTitle = titulo[:63]
        d.szInfo = texto[:255]
        d.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON if self.hicon else NIIF_INFO
        d.hBalloonIcon = self.hicon
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    # --- mensajes -----------------------------------------------------------
    def _menu(self) -> None:
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, self.titulo)
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_ABRIR, "Abrir panel")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_CERRAR, "Cerrar todo")
        user32.SetMenuDefaultItem(menu, CMD_ABRIR, 0)
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)  # necesario para que el menú se cierre al hacer clic afuera
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY | TPM_BOTTOMALIGN,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if cmd == CMD_ABRIR:
            threading.Thread(target=self.al_abrir, daemon=True).start()
        elif cmd == CMD_CERRAR:
            threading.Thread(target=self.al_cerrar, daemon=True).start()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_BANDEJA:
                evento = lparam & 0xFFFF
                if evento == WM_RBUTTONUP:
                    self._menu()
                elif evento == WM_LBUTTONDBLCLK:
                    threading.Thread(target=self.al_abrir, daemon=True).start()
                return 0
            if msg == self._msg_taskbar and self._msg_taskbar:
                self._agregar_icono()
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._datos()))
                user32.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001 — una excepción aquí cerraría el proceso
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
