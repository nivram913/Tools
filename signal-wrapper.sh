#! /bin/bash

cleanup() {
    rsync -a --delete /home/nivram/.config/Signal/* /home/nivram/.config/Signal.real/
    #pkexec umount /home/nivram/.config/Signal
    rm -rf /run/user/1000/Signal /home/nivram/.config/Signal
}

#pkexec mount -t tmpfs -o size=128m tmpfs /home/nivram/.config/Signal || exit 1
mkdir /run/user/1000/Signal
ln -s /run/user/1000/Signal/ /home/nivram/.config/Signal
rsync -a --delete /home/nivram/.config/Signal.real/* /home/nivram/.config/Signal/
trap cleanup EXIT

signal-desktop 1>&2 > /dev/null

exit 0
