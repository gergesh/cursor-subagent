/*
 * Cursor directory redirection dylib using DYLD_INTERPOSE
 * Intercepts file system calls to redirect .cursor directory access
 */

#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

// DYLD_INTERPOSE macro for macOS
#define DYLD_INTERPOSE(_replacement,_replacee) \
    __attribute__((used)) static struct{ const void* replacement; const void* replacee; } _interpose_##_replacee \
    __attribute__ ((section ("__DATA,__interpose"))) = { (const void*)(unsigned long)&_replacement, (const void*)(unsigned long)&_replacee };

// Macro to wrap interposed functions with redirection logic
#define INTERPOSE_WRAPPER(name, call_expr) \
    char buffer[4096]; \
    const char *final_path = redirect_path(path, buffer, sizeof(buffer)); \
    in_redirect = 1; \
    typeof(call_expr) result = call_expr; \
    in_redirect = 0; \
    return result;

// Environment variables
static const char *ENV_SOURCE = "CURSOR_REDIRECT_SOURCE";
static const char *ENV_TARGET = "CURSOR_REDIRECT_TARGET";

// Cached paths
static char *source_path = NULL;
static char *target_path = NULL;
static int initialized = 0;

// Thread-local to prevent recursion
static __thread int in_redirect = 0;

// Initialize paths from environment
static void init_paths() {
    if (initialized) return;
    initialized = 1;

    source_path = getenv(ENV_SOURCE);
    target_path = getenv(ENV_TARGET);

#ifdef DEBUG_REDIRECT
    if (source_path && target_path) {
        fprintf(stderr, "[REDIRECT-INIT] Source: %s\n", source_path);
        fprintf(stderr, "[REDIRECT-INIT] Target: %s\n", target_path);
    } else {
        fprintf(stderr, "[REDIRECT-INIT] Environment variables not set\n");
    }
#endif
}

// Redirect path if it matches source
static const char *redirect_path(const char *path, char *buffer, size_t buf_size) {
    if (in_redirect || !path) return path;

    init_paths();

    if (!source_path || !target_path) {
        return path;
    }

    size_t src_len = strlen(source_path);
    size_t path_len = strlen(path);

    // Special case: .cursorrules file in root should redirect to subagent/.cursorrules
    if (path_len > 13 && strcmp(path + path_len - 13, "/.cursorrules") == 0) {
        // Check if this is NOT already in the .cursor/subagents path
        if (strstr(path, "/.cursor/subagents/") == NULL) {
            size_t tgt_len = strlen(target_path);
            if (tgt_len + 14 > buf_size) {
                return path; // Buffer too small
            }

            memcpy(buffer, target_path, tgt_len);
            memcpy(buffer + tgt_len, "/.cursorrules", 14);

#ifdef DEBUG_REDIRECT
            fprintf(stderr, "[REDIRECT] %s\n", path);
            fprintf(stderr, "[REDIRECT]  -> %s\n", buffer);
#endif

            return buffer;
        }
    }

    // Check if path starts with source_path
    if (strncmp(path, source_path, src_len) == 0) {
        // Ensure it's followed by a slash or is exact match
        if (path[src_len] == '/' || path[src_len] == '\0') {
            const char *suffix = path + src_len;
            size_t tgt_len = strlen(target_path);
            size_t suffix_len = strlen(suffix);

            if (tgt_len + suffix_len + 1 > buf_size) {
                return path; // Buffer too small
            }

            // Build redirected path
            memcpy(buffer, target_path, tgt_len);
            memcpy(buffer + tgt_len, suffix, suffix_len);
            buffer[tgt_len + suffix_len] = '\0';

#ifdef DEBUG_REDIRECT
            fprintf(stderr, "[REDIRECT] %s\n", path);
            fprintf(stderr, "[REDIRECT]  -> %s\n", buffer);
#endif

            return buffer;
        }
    }

    return path;
}

// Interposed functions using macro for common logic
int my_stat(const char *path, struct stat *buf) {
    INTERPOSE_WRAPPER(stat, stat(final_path, buf))
}

int my_lstat(const char *path, struct stat *buf) {
    INTERPOSE_WRAPPER(lstat, lstat(final_path, buf))
}

int my_access(const char *path, int mode) {
    INTERPOSE_WRAPPER(access, access(final_path, mode))
}

ssize_t my_readlink(const char *path, char *buf, size_t bufsiz) {
    INTERPOSE_WRAPPER(readlink, readlink(final_path, buf, bufsiz))
}

char *my_realpath(const char *path, char *resolved_path) {
    INTERPOSE_WRAPPER(realpath, realpath(final_path, resolved_path))
}

// open() needs special handling for variadic args
int my_open(const char *path, int flags, ...) {
    char buffer[4096];
    const char *final_path = redirect_path(path, buffer, sizeof(buffer));

    in_redirect = 1;

    int result;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, int);
        va_end(args);
        result = open(final_path, flags, mode);
    } else {
        result = open(final_path, flags);
    }

    in_redirect = 0;
    return result;
}

// openat() needs special handling for variadic args
int my_openat(int fd, const char *path, int flags, ...) {
    char buffer[4096];
    const char *final_path = redirect_path(path, buffer, sizeof(buffer));

    in_redirect = 1;

    int result;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode_t mode = va_arg(args, int);
        va_end(args);
        result = openat(fd, final_path, flags, mode);
    } else {
        result = openat(fd, final_path, flags);
    }

    in_redirect = 0;
    return result;
}

// Register interpositions
DYLD_INTERPOSE(my_open, open)
DYLD_INTERPOSE(my_openat, openat)
DYLD_INTERPOSE(my_stat, stat)
DYLD_INTERPOSE(my_lstat, lstat)
DYLD_INTERPOSE(my_access, access)
DYLD_INTERPOSE(my_readlink, readlink)
DYLD_INTERPOSE(my_realpath, realpath)
