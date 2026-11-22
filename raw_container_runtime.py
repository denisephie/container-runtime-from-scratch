import os, ctypes, sys, socket, secrets, shutil, tarfile, argparse, hashlib, tempfile

libc = ctypes.CDLL('libc.so.6', use_errno=True)

runtime_path = "/var/lib/container-runtime"

parser = argparse.ArgumentParser(
                    prog='containphie runtime',
                    description='toples lariwaktu, masih dalam progres',
                    epilog='sekian trims <3')

commands = parser.add_subparsers(dest="command", required=True)
image_parser = commands.add_parser("image", help="manage images")
run_parser = commands.add_parser("run", help="run container from images")

image_commands = image_parser.add_subparsers(dest="image_command", required=True)

#run_commands = run_parser.add_subparsers(dest="run_command", required=True)
#run_tag_parser = run_commands.add_parser("build", help="build tag files")
#run_tag_parser.add_argument("tag")

# import operation
image_import_parser = image_commands.add_parser("import", help="import rootfs archive")

# arguments for import operation
image_import_parser.add_argument("tarball_path", help="path to local tarball")
image_import_parser.add_argument("tag", help="tag to assign, e.g alpine:local")

run_parser.add_argument("image_reference", help="image tag or image id, e.g alpine:local")
# this gives -> sudo python3 script.py run alpine:local

args = parser.parse_args()

def custom_tarfilter(member, dest_path):
    original = member.mode #unmodified mode bfore filter  
    filtered = tarfile.tar_filter(member, dest_path)
    saved_final = filtered.replace(mode=original)
    return saved_final

def take_tarball(tarball_path_passed):
    runtime_path = "/var/lib/container-runtime"
    image_path = os.path.join(runtime_path, "images")
    #ext_folder = os.path.join()
    imports_path = os.path.join(runtime_path, "imports")

    for i in [image_path, imports_path]:
        os.makedirs(i, exist_ok=True)

    #extract the tarball (.tar.gz) that already exists on the disk 
    tarball_path = tarball_path_passed
    digest = hashlib.sha256() # return sha-256 hash object (not value), has internal state
    with open(tarball_path, "rb") as file:
        while True:
            block = file.read(1024 * 1024)

            if not block:
                break
            digest.update(block) # append block to the sha-256 hash object's internal buffer
    image_id = digest.hexdigest() # converts sha-256 binary digest into a string of hexadecimal digits
    image_dir = os.path.join(image_path, image_id)
    rootfs_path = os.path.join(image_dir, "rootfs")
    if os.path.isdir(rootfs_path):
        print("image already exists")
    else:
        temp_path = tempfile.mkdtemp(dir=imports_path) # unique temp dir on same filesys as the dest
        try:
            with tarfile.open(tarball_path, "r:*") as tar:
                tar.extractall(path=temp_path, filter=custom_tarfilter)
                os.makedirs(image_dir, exist_ok=True)
                os.replace(temp_path, rootfs_path)
        except (tarfile.TarError, OSError, EOFError) as err:
            shutil.rmtree(temp_path, ignore_errors=True)
            sys.exit(f"{err}: import failed")
        finally: 
            if os.path.isdir(temp_path):
                shutil.rmtree(temp_path)
    return image_id, image_dir

def image_tag(tag_passed, image_id):
    if tag_passed == "":
        sys.exit("tag is empty")
    elif tag_passed in (".", ".."):
        sys.exit("invalid tag name")
    elif "/" in tag_passed or "\0" in tag_passed:
        sys.exit("invalid tag name")
    else:
        tags_path = os.path.join(runtime_path, "tags")
        tag_file = os.path.join(tags_path, tag_passed)
        os.makedirs(tags_path, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=tags_path) # temporary file
        try:
            with os.fdopen(fd, "w") as file:
                file.write(image_id)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, tag_file)
        except OSError as err:
            sys.exit(f"{err}: retag failed")
        finally:
            if os.path.isfile(temp_path):
                os.unlink(temp_path)
    return tag_file

def command(cont_new_root):
    rootfs = os.path.abspath(cont_new_root)
    shell_path = os.path.join(rootfs, "bin", "sh")
    container_base = secrets.token_hex()
    cgroup_path = os.path.join("/sys/fs/cgroup/", container_base)
    upper, work, merged = [secrets.token_hex() for i in range(3)]
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

    runtime_path = "/var/lib/container-runtime"
    base_path = os.path.join(runtime_path,container_base)
    #lowerdir_path = os.path.join(base_path, "lower")
    upperdir_path = os.path.join(base_path, upper)
    workdir_path = os.path.join(base_path, work)
    merged_path = os.path.join(base_path, merged)

    for i in [upperdir_path, workdir_path, merged_path]:
        os.makedirs(i, exist_ok=False)
    image_mount = os.fsencode(f"lowerdir={rootfs},upperdir={upperdir_path},workdir={workdir_path}")

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
                mp_encoded = os.fsencode(merged_path)
                image_to_mount = libc.mount(b"overlay", mp_encoded, b"overlay", 0, image_mount)
                if image_to_mount != 0:
                    err_im = ctypes.get_errno()
                    raise OSError (err_im, "merged mount failed")
                else:
                    put_old = "put_old"
                    old_root = os.path.join(merged_path, put_old) #/put_old
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
                '''
                rootpath = os.path.abspath(cont_new_root)
                encoded_path = os.fsencode(rootpath)
                MS_BIND = 4096
                ret_2 = libc.mount(encoded_path, encoded_path, None, MS_BIND | MS_REC, None)
                if ret_2 != 0:
                    err_2 = ctypes.get_errno()
                    raise OSError(err_2, "mount failed")
                '''
                # place new root (rootfs) into new namespace
                encoded_oldroot = os.fsencode(old_root)
                a = libc.syscall(SYS_pivot_root, mp_encoded, encoded_oldroot)
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
        try:
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
        finally:
            try:
                os.rmdir(cgroup_path)
            except OSError as e:
                print(f"failed to remove cgroup {cgroup_path}: {e}", file=sys.stderr, flush=True)
            try:
                shutil.rmtree(base_path)
            except OSError as e:
                print(f"failed to remove {base_path}: {e}", file=sys.stderr, flush=True)
        exit_code1 = os.waitstatus_to_exitcode(status1) #signal death is returned as negative that is wrapped by os to 247 that means nothing (check notion for code meanings)
        if os.WIFSIGNALED(status1):
            print("Child proc exited with code: ", (128-exit_code1), flush=True)
            return (128-exit_code1)
        else: 
            return exit_code1


if __name__ == "__main__":
    if args.command == "image":
        if args.image_command == "import":
            image_id, image_dir = take_tarball(args.tarball_path)
            tag_file = image_tag(args.tag, image_id)
            print(image_id, image_dir, tag_file)
    elif args.command == "run":
        sys.exit(command(args.image_reference))