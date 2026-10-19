//go:build linux

package volcopy

import (
	"fmt"
	"io/fs"
	"os"
	"syscall"
	"unsafe"
)

// metaOf reads what the digest and the copy use from an Lstat.
func metaOf(fi fs.FileInfo) (meta, error) {
	s, ok := fi.Sys().(*syscall.Stat_t)
	if !ok {
		return meta{}, fmt.Errorf("%s: no stat_t from lstat", fi.Name())
	}
	return meta{
		mode: s.Mode, uid: s.Uid, gid: s.Gid,
		atime: s.Atim.Nano(), mtime: s.Mtim.Nano(), size: s.Size,
		dev: uint64(s.Dev), ino: uint64(s.Ino), nlink: uint64(s.Nlink),
	}, nil
}

// utimensat's arguments, from linux/fcntl.h (the same on every architecture); the syscall package does not export
// them.
const (
	atFDCWD           = -0x64
	atSymlinkNofollow = 0x100
)

// lutimes sets p's access and modification times without following a link: utimensat(2) with AT_SYMLINK_NOFOLLOW,
// which the syscall package does not wrap (its UtimesNano follows one).
func lutimes(p string, atime, mtime int64) error {
	ts := [2]syscall.Timespec{syscall.NsecToTimespec(atime), syscall.NsecToTimespec(mtime)}
	b, err := syscall.BytePtrFromString(p)
	if err != nil {
		return err
	}
	cwd := atFDCWD
	_, _, e := syscall.Syscall6(syscall.SYS_UTIMENSAT, uintptr(cwd), uintptr(unsafe.Pointer(b)),
		uintptr(unsafe.Pointer(&ts[0])), atSymlinkNofollow, 0, 0)
	if e != 0 {
		return &os.PathError{Op: "utimensat", Path: p, Err: e}
	}
	return nil
}
