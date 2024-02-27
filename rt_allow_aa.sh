#!/bin/bash

cleanup() {
    rm -rf /home/nivram/Public/Firefox/tmp_aa_allow
}

watch_dmesg_for_aa_deny_events() {
    dmesg -w | grep --line-buffered -Eo 'apparmor="DENIED" operation="open" profile="firefox" name="/home/[^"]*"' | grep --line-buffered -Eo '/home/[^"]*'
}

mkdir /home/nivram/Public/Firefox/tmp_aa_allow
trap cleanup EXIT

watch_dmesg_for_aa_deny_events | while read file
do
    zenity --question --no-wrap --title="AppArmor Policy Violation" --text="Firefox tried to access $file. Do you want to allow it ?" --ok-label="Allow" --cancel-label="Deny"
    if (($? == 0))
    then
        ln "$file" /home/nivram/Public/Firefox/tmp_aa_allow/"$(basename "$file")"
    fi
done
