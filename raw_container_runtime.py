import os 
import ctypes 

libc = ctypes.CDLL('libc.so.6', use_errno=True)

def command(): 
    pid = os.fork() 
    if pid == 0: #child
        os.unshare(os.CLONE_NEWUTS | os.CLONE_NEWPID | os.CLONE_NEWNS)
        fix_proc = os.fork() #the proc we want to isolate -> bcomes PID 1
        if fix_proc == 0:
            os.sethostname(b"legleg-ubuntu")

            #mount flags - to recursively make the mount tree private (usually used after unshare)
            MS_REC = 16384 #recursive
            MS_PRIVATE = 1 << 18 #make private
            ret = libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
            if ret != 0:
                err = ctypes.get_errno()
                raise OSError(err, "mount failed")
            
            else:
                MS_BIND = 4096
                ret_2 = libc.mount(b"/", b"/", None, MS_BIND | MS_REC, None)
                if ret_2 != 0:
                    err_2 = ctypes.get_errno()
                    raise OSError(err_2, "mount failed")
                
                else:
                    os.mkdir(b"/put_old", exist_ok=True)
                    ARCH = os.uname().machine
                    if ARCH == "x86_64":
                        SYS_pivot_root = 155
                    elif ARCH in ("aarch64", "arm64", "riscv64"):
                        SYS_pivot_root = 41
                    elif ARCH in ("i386", "i686"):
                        SYS_pivot_root = 217
                    else:
                        raise RuntimeError(f"CPU Architecture not supported: {ARCH}")

                libc.mount.argtypes = [ #to specify type of data passed in
                    ctypes.c_char_p, #points to immutable string -> read-only c strings
                    ctypes.c_char_p,
                    ctypes.c_char_p,
                    ctypes.c_ulong, #unsigned long integers
                    ctypes.c_void_p #
                ]
                libc.mount.restype = ctypes.c_int #type to return
                
        else: 
           os.waitpid(fix_proc, 0) #pause until child process whose pid in fix_proc exits)
    else: #parent
        os.waitpid(pid, 0)
    return 





    