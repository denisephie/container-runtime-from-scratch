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