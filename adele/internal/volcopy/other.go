//go:build !linux

package volcopy

import (
	"errors"
	"fmt"
)

// The helper runs in Adele's Linux image only; elsewhere the package builds and every call refuses.

var errPlatform = fmt.Errorf("volcopy: %w on this platform (the helper runs on Linux)", errors.ErrUnsupported)

func Measure(string) (Stats, error)              { return Stats{}, errPlatform }
func Digest(string) (Stats, string, error)       { return Stats{}, "", errPlatform }
func Copy(string, string, int64) (Result, error) { return Result{}, errPlatform }
func Restore(string, string) (Result, error)     { return Result{}, errPlatform }
