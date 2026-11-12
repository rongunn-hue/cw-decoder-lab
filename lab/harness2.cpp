// harness2: raw float32 mono 4000 Hz stdin -> text. argv: floor_db [slow] ; env CW_OLD=1 uses old text path if built with it
#include "receiver.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
int main(int argc, char **argv) {
    float floor_db = argc > 1 ? atof(argv[1]) : 5.0f;
    bool slow = argc > 2 && !strcmp(argv[2], "slow");
    cw::Receiver rx([](const char *t, bool) { fputs(t, stdout); fflush(stdout); }, {}, {});
    rx.set_floor_db(floor_db); rx.set_band(300.0f, 1500.0f);
    if (slow) rx.trainer_range(true);
    std::vector<float> buf(4000); size_t n;
    while ((n = fread(buf.data(), 4, buf.size(), stdin)) > 0) rx.feed(buf.data(), n);
    fputs("\n", stdout);
}
