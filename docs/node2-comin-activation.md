# Node2 Comin activation

The imported image enables SSH and Comin separately from `lab.enable`, but the old node2 leaf disabled them. The correction enables only SSH, the existing normal `operator` account, and marker-gated Comin in node2's deployment module. It declares IPv6 TCP22 in the guest firewall and preserves the host-local authorized-key file. `lab.enable` remains false; WireGuard, telemetry, Wasm and Kubernetes remain off. No user/key, password, sudo privilege, bootloader, filesystem or Azure network change is introduced.

The shared Azure runtime module remains imported by the actual node2 target. It retains Gen2 GRUB, Hyper-V initrd drivers, networkd, ext4 root by label `nixos` and vfat boot by label `ESP` (reported on the canary as `/dev/sda2` and `/dev/sda1`). Do not replace those mounts with the QEMU test fixture's boot configuration.

The new VM test starts from the image's bare/marker-gated service behavior, activates the actual node2 deployment module through Comin using a prebuilt NixOS generation, then verifies SSH after firewall restart and reboot. It proves neither Hyper-V hardware emulation nor compiling the complete generation inside 1 GiB. Actual leaf Azure hardware is checked by Nix evaluation separately.

## Privileged bootstrap, proposed only

First publish/review/test/merge the corrected leaf. Do not create the marker while main still contains the disabling leaf. Confirm the active generation and SSH host key remain recoverable.

The existing `operator` account cannot create the root-owned marker, and passwordless sudo was observed to fail. Starting Comin is therefore not possible through the current unprivileged SSH connection alone. Do not enable root/password SSH or assume Azure extensions/RunCommand work on this image.

Preferred candidate: a one-time Azure Serial Console/GRUB recovery session using the existing administrator, after explicit approval for temporary root console access and a brief reboot. First verify console/GRUB accessibility and the installed initrd/systemd version using read-only evidence. The pinned NixOS source enables systemd initrd and includes its breakpoint/debug-shell units; upstream systemd supports a transient pre-switch-root breakpoint with a selected console. These facts do not prove access to this live VM's boot console.

If confirmed and approved, edit only the current GRUB boot entry with `rd.systemd.break=pre-switch-root rd.systemd.default_debug_tty=ttyS0`. Do not save this as a persistent kernel parameter. At the root breakpoint, verify `/sysroot` is the intended node2 filesystem, remount it writable if necessary, and create only `/sysroot/var/lib/fleet-access/bootstrap-approved`, root-owned mode0600. Sync and exit the breakpoint to resume normal boot. Comin's existing enabled unit will see the marker and reconcile the reviewed node2 leaf. Verify SSH, active generation, Comin journal and absence of debug parameters on the subsequent ordinary reboot. Do not create a password or sudo rule.

This temporarily grants unauthenticated root access to the authenticated Azure console operator; it is a privileged recovery operation and interrupts SSH during reboot. If console access or the breakpoint is unavailable, stop: offline-disk repair or a qualified extension would require a different explicit scope, permissions and cost review. No such fallback is authorized by this document.

Sources: [Azure GRUB/serial recovery](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/serial-console-grub-single-user-mode), [systemd breakpoints](https://www.freedesktop.org/software/systemd/man/latest/systemd-debug-generator.html), [pinned NixOS initrd](https://github.com/NixOS/nixpkgs/blob/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36/nixos/modules/system/boot/systemd/initrd.nix).
