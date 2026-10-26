import os
import ctypes
import sys

libc = ctypes.CDLL('libc.so.6', use_errno=True)

def command():
    pid = os.fork()
    if pid == 0: #child
        os.unshare(os.CLONE_NEWUTS | os.CLONE_NEWPID | os.CLONE_NEWNS)
        fix_proc = os.fork() #the proc we want to isolate -> bcomes PID 1
        if fix_proc == 0:
            os.sethostname(b"legleg-ubuntu")

            #specify passed argument and returned data types before any libc.mount are use d
            libc.mount.argtypes = [ #to specify type of data passed in
                    ctypes.c_char_p, #points to immutable string -> read-only c strings
                    ctypes.c_char_p,
                    ctypes.c_char_p,
                    ctypes.c_ulong, #unsigned long integers
                    ctypes.c_void_p
            ]
            libc.mount.restype = ctypes.c_int #type to return            
            #mount flags - to recursively make the mount tree private (usually used after unshare)
            MS_REC = 16384 #recursive
            MS_PRIVATE = 1 << 18 #make private
            ret = libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
            if ret != 0:
                err = ctypes.get_errno()
                raise OSError(err, "mount failed")
           
            else: #make rootfs into mount point here (during self-bind)
                script_name = sys.argv[0]
                rootpath = os.path.abspath(sys.argv[1])
                encoded_path = os.fsencode(rootpath)
                MS_BIND = 4096
                ret_2 = libc.mount(encoded_path, encoded_path, None, MS_BIND | MS_REC, None)
                if ret_2 != 0:
                    err_2 = ctypes.get_errno()
                    raise OSError(err_2, "mount failed")
               
                else:
                    put_old = "put_old"
                    old_root = os.path.join(rootpath, put_old) #/mnt/alpine-rootfs
                    os.makedirs(old_root, exist_ok=True) #makedirs can ignore existent file path error
                    ARCH = os.uname().machine
                    if ARCH == "x86_64":
                        SYS_pivot_root = 155
                    elif ARCH in ("aarch64", "arm64", "riscv64"):
                        SYS_pivot_root = 41
                    elif ARCH in ("i386", "i686"):
                        SYS_pivot_root = 217
                    else:
                        raise RuntimeError(f"CPU Architecture not supported: {ARCH}")
                # place new root (rootfs) into new namespace
                encoded_oldroot = os.fsencode(old_root)
                a = libc.syscall(SYS_pivot_root, encoded_path, encoded_oldroot)
                if a != 0:
                    err_3 = ctypes.get_errno()
                    raise OSError(err_3, f"pivot_root failed: {os.strerror(err_3)}")
                os.chdir("/")
                MNT_DETACH = 2
                ret_3 = libc.umount2(b"/put_old", MNT_DETACH) #umount2 allows flags
                if ret_3 != 0:
                    err_4 = ctypes.get_errno()
                    raise OSError(err_4, f"unmount failed: {os.strerror(err_4)}")
                os.rmdir("/put_old")
                libc.mount(b"proc", b"/proc", b"proc", 0, None)
                os.execv(b"/bin/sh", ["/bin/sh"])
        else:
           os.waitpid(fix_proc, 0) #pause until child process whose pid in fix_proc exits

    else: #parent
        os.waitpid(pid, 0)
    return