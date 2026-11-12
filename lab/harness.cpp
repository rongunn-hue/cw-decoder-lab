// Standalone harness: raw float32 mono 4000 Hz on stdin -> decoded text on stdout (no squelch).
#include "receiver.h"
#include <cstdio>
#include <vector>
int main(int argc, char **argv) {
    float floor_db = argc > 1 ? atof(argv[1]) : 5.0f;
    cw::Receiver rx([](const char *t, bool) { fputs(t, stdout); fflush(stdout); }, {}, {});
    rx.set_floor_db(floor_db);
    rx.set_band(300.0f, 1500.0f);
    std::vector<float> buf(4000);
    size_t n;
    while ((n = fread(buf.data(), 4, buf.size(), stdin)) > 0) rx.feed(buf.data(), n);
    fputs("\n", stdout);
    fprintf(stderr, "final wpm %.1f lock %.1f Hz\n", rx.wpm(), rx.lock_hz());
}
