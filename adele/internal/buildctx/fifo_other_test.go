//go:build !unix

package buildctx

import "errors"

func mkfifo(string) error { return errors.New("no fifo on this platform") }
