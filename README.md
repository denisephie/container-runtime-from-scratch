### An attempt in learning more about what makes a container.. a container :^) 

Run script into VM (VM originally used: Lima - Ubuntu)

1. Create a dedicated VM
```bash 
limactl start --name=placeholder template://ubuntu
limactl list # to view active VMs
```
2. Shell into the created VM
```bash
limactl shell placeholder # use the shell inside the VM
```
Here we can do a passwordless `sudo` so there is no need to log in as root 

3. Do checks 
```bash
python3 --version
uname -m # machine hardware name 
mount | grep cgroup2 
```

4. Run file using `sudo python3 filename.py`

5. Clean-up and Reset
```bash
limactl stop placeholder 
limactl delete placeholder
```
6. Checks from Host Side -> Use another terminal session's `ps` and `hostname`

Getting alpine-rootfs and extracting the tarball inside VM

1. Open https://alpinelinux.org/downloads/ and navigate until "Mini Root Filesystem" is found 

2. Navigate to the appropriate mini root filesys according to your VM machine hardware name (checked using `uname -m` inside the VM) and copy link address

3. Open the VM's shell using `limactl shell placeholder` 

4. `cd ~` inside the VM's shell to change current working directory to home, and `pwd` to check if you are in the correct directory (e.g, /home/name.guest)

5. Download the mini root filesystem using the link address that was copied previously with `wget link-address`

6. Create a directory to put the root filesystem
``` bash
mkdir -p /mnt/alpine-rootfs
```

7. Extract the tarball that was downloaded previously inside the new directory
```bash
sudo tar -xzf tarball-name -C /mnt/alpine-rootfs
```

8. `ls /mnt/alpine-rootfs` and check if `bin`, `dev`, `etc`, and others are included inside, if yes, then all is good :)
