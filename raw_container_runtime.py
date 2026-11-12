import os
import ctypes
import sys
import socket

libc = ctypes.CDLL('libc.so.6', use_errno=True)

def command(cont_new_root):
    rootfs = os.path.abspath(cont_new_root)
    shell_path = os.path.join(rootfs, "bin", "sh")
    cgroup_path = "/sys/fs/cgroup/containphie"
    r_pid, w_pid = os.pipe() # pipe for child to give gc pid to parent
    r_go, w_go = os.pipe() # pipe for parent to give go to grandchild
    if not os.path.isdir(rootfs): 
        sys.exit(f"{rootfs} does not exist")
    if not os.path.lexists(shell_path): 
        sys.exit("/bin/sh does not exist")
    #if not os.access(shell_path, os.X_OK):
        #sys.exit("/bin/sh is not executable")
    if not os.path.isdir(os.path.join(rootfs,"proc")):
        sys.exit("/proc does not exist")
    
    pid = os.fork()
    if pid == 0: #child
        os.unshare(os.CLONE_NEWUTS | os.CLONE_NEWPID | os.CLONE_NEWNS) #disassociate parts of exec context that it currently shares w other procs
        fix_proc = os.fork() #the proc we want to isolate -> bcomes PID 1
        if fix_proc == 0: #grandchild
            os.close(r_pid)
            os.close(w_pid)
            os.close(w_go)
            os.read(r_go, 1) #block on pipe
            os.close(r_go)
            socket.sethostname(b"legleg-ubuntu")


            #specify passed argument and returned data types before any libc.mount are used - more info in notion notes
            libc.mount.argtypes = [ #to specify type of data passed in
                    ctypes.c_char_p, #points to immutable byte string -> read-only c strings
                    ctypes.c_char_p, 
                    ctypes.c_char_p, 
                    ctypes.c_ulong, #mount flags, unsigned long integers
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
                rootpath = os.path.abspath(cont_new_root)
                encoded_path = os.fsencode(rootpath)
                MS_BIND = 4096
                ret_2 = libc.mount(encoded_path, encoded_path, None, MS_BIND | MS_REC, None)
                if ret_2 != 0:
                    err_2 = ctypes.get_errno()
                    raise OSError(err_2, "mount failed")
               
                else:
                    put_old = "put_old"
                    old_root = os.path.join(rootpath, put_old) #/put_old
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
                libc.mount(b"proc", b"proc", b"proc", 0, None)
                os.execv(b"/bin/sh", ["/bin/sh"])
        else:
           os.close(r_go)
           os.close(w_go)
           os.close(r_pid)
           os.write(w_pid, str(fix_proc).encode())
           os.close(w_pid)
           grandchild, status2 = os.waitpid(fix_proc, 0) #pause until child process whose pid in fix_proc exits
           exit_code2 = os.waitstatus_to_exitcode(status2) #convert status to code
           if os.WIFSIGNALED(status2):
                 print("Grandchild proc exited with code: ", (128-exit_code2), flush=True)
                 os._exit(128-exit_code2)
           else:
                 print("Grandchild proc exited with code: ", exit_code2, flush=True)
                 os._exit(exit_code2)
    else: #parent
        os.makedirs(cgroup_path, exist_ok=True)
        os.close(w_pid)
        gc_pid = int(os.read(r_pid, 32).decode())
        os.close(r_pid)
        with open(os.path.join(cgroup_path, "memory.max"), "w") as i:
            i.write(str(512 * 1024 * 1024))
        with open(os.path.join(cgroup_path, "pids.max"), "w") as i:
            i.write("128")
        with open(os.path.join(cgroup_path, "cpu.max"), "w") as i:
            i.write("100000 100000")
        with open(os.path.join(cgroup_path, "cgroup.procs"), "w") as i:
            i.write(str(gc_pid))
        os.close(r_go)
        #error handling (?)
        os.write(w_go, b"1") # write 1 byte to trigger os.read r_go in grandchild
        os.close(w_go)
        child, status1 = os.waitpid(pid, 0)
        os.rmdir(cgroup_path)
        exit_code1 = os.waitstatus_to_exitcode(status1) #signal death is returned as negative that is wrapped by os to 247 that means nothing (check notion for code meanings)
        if os.WIFSIGNALED(status1):
            print("Child proc exited with code: ", (128-exit_code1), flush=True)
            return (128-exit_code1)
        else: 
            return exit_code1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Argument not valid")
    correct = command(sys.argv[1])
    sys.exit(correct)