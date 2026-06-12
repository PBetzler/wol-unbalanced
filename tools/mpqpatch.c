// mpqpatch — replace (or add) a single file inside an MPQ archive (SC2Map/SC2Mod).
// Usage: mpqpatch <archive.SC2Map> <local-file> <archived-name>
// Example: mpqpatch traynor01.SC2Map /tmp/DocumentInfo DocumentInfo
#include <stdio.h>
#include <StormLib.h>

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s <archive> <local-file> <archived-name>\n", argv[0]);
        return 2;
    }
    HANDLE mpq = NULL;
    if (!SFileOpenArchive(argv[1], 0, 0, &mpq)) {
        fprintf(stderr, "open '%s' failed, err=%u\n", argv[1], SErrGetLastError());
        return 1;
    }
    if (!SFileAddFileEx(mpq, argv[2], argv[3],
                        MPQ_FILE_COMPRESS | MPQ_FILE_REPLACEEXISTING,
                        MPQ_COMPRESSION_ZLIB, MPQ_COMPRESSION_NEXT_SAME)) {
        fprintf(stderr, "add '%s' as '%s' failed, err=%u\n", argv[2], argv[3], SErrGetLastError());
        SFileCloseArchive(mpq);
        return 1;
    }
    if (!SFileCompactArchive(mpq, NULL, 0))
        fprintf(stderr, "warning: compact failed, err=%u (archive still valid)\n", SErrGetLastError());
    SFileCloseArchive(mpq);
    printf("patched %s: %s <- %s\n", argv[1], argv[3], argv[2]);
    return 0;
}
