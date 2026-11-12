/*  SPDX-License-Identifier: LGPL-2.1-or-later
 *  cwlab revision 1: derived from OpenX6X00 src/cw_decoder (itself derived from gdyuldin x6100_gui). New files:
 *  soft_decoder.*, cw_lm.h. Changed: receiver.*, element_timer.h (dot_ms accessor). */
/* Causal word-at-a-time likelihood decoder for hand-sent Morse (cwlab revision 1).
 * Input: every closed mark/gap duration. Output: text, one word at a time, when a word gap is reached.
 * No hard dit/dah or gap thresholds: each interval is scored under {dit,dah} / {element,char,word gap} with locally
 * estimated centres, and a beam search over character paths picks the most likely text. */
#pragma once
#include <functional>
#include <string>
#include <vector>

namespace cw {

class SoftDecoder {
  public:
    using Out = std::function<void(const char *text, bool own)>;
    explicit SoftDecoder(Out out) : out_(std::move(out)) {}

    /* A mark or gap has just closed. prior_dit_ms: the speed the element timer currently believes. */
    void interval(bool mark, float ms, bool strong, float prior_dit_ms);
    /* Called every detector step with the running gap length while key is up (idle end-of-text) */
    void idle(float gap_ms, float prior_dit_ms);

    float dit_ms() const { return p_.dit; }

  private:
    struct Params { float dit = 60, dah = 180, eg = 60, cg = 180, wg = 420, sd_m = 0.28f, sd_g = 0.32f; };
    struct Iv { bool mark; float ms; };

    void estimate(float prior_dit);
    void decode_pending(bool final_is_word);
    void emit(const std::string &s);

    Out out_;
    std::vector<Iv> hist_;      /* recent closed intervals (parameter estimation), capped */
    std::vector<Iv> pending_;   /* intervals of the word being collected, starts with a mark */
    Params p_;
    bool flushed_ = true;       /* the current idle gap already ended the word */
    float carry_gap_ = 0;       /* gap time swallowed by an ignored blip */
    bool last_space_ = true;
};

} // namespace cw
