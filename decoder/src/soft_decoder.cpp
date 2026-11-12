/*  SPDX-License-Identifier: LGPL-2.1-or-later
 *  cwlab revision 1: derived from OpenX6X00 src/cw_decoder (itself derived from gdyuldin x6100_gui). New files:
 *  soft_decoder.*, cw_lm.h. Changed: receiver.*, element_timer.h (dot_ms accessor). */
#include "soft_decoder.h"
#include "morse_code.h"
#include "cw_lm.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>

namespace cw {
namespace {

constexpr size_t HIST_MAX   = 64;
constexpr size_t PEND_MAX   = 96;   /* force a decode when a word has this many intervals */
constexpr size_t BEAM       = 200;
constexpr float  SD_MARK    = 0.28f;
constexpr float  SD_GAP     = 0.32f;
constexpr float  SD_MIN     = 0.10f;
constexpr float  SD_MAX     = 0.45f;
constexpr float  INVALID    = -9.0f;
constexpr float  BLIP_K     = 0.30f;   /* a mark shorter than this many dits is noise */
constexpr float  CARRIER_K  = 8.0f;    /* a mark longer than this many dahs/dits... in dits */

float ll(float x, float c, float sd) {
    float d = (std::log(x) - std::log(c)) / sd;
    return -0.5f * d * d;
}

/* log prior of a decoded symbol: letters ~English frequency, digits and punctuation rarer */
float lm(const char *t) {
    static const char *order = "ETAOINSHRDLCUMWFGYPBVKJXQZ";
    static const float freq[] = {12.7f, 9.1f, 8.2f, 7.5f, 7.0f, 6.7f, 6.3f, 6.1f, 6.0f, 4.3f, 4.0f, 2.8f, 2.8f, 2.4f, 2.4f,
                                 2.2f, 2.0f, 2.0f, 1.9f, 1.5f, 1.0f, 0.8f, 0.15f, 0.15f, 0.1f, 0.07f};
    if (t[0] && !t[1]) {
        const char *p = std::strchr(order, t[0]);
        if (p) return std::log(freq[p - order] / 100.0f);
        if (t[0] >= '0' && t[0] <= '9') return std::log(0.01f);
        return std::log(0.002f);
    }
    return std::log(0.002f);   /* prosigns */
}

/* 1-D 2-means on a small vector; centres sorted ascending; returns false if degenerate */
bool two_means(std::vector<float> x, float &c0, float &c1) {
    if (x.size() < 2) return false;
    std::sort(x.begin(), x.end());
    c0 = x[x.size() / 4]; c1 = x[std::min(x.size() - 1, x.size() * 85 / 100)];
    for (int it = 0; it < 20; it++) {
        double s0 = 0, s1 = 0; int n0 = 0, n1 = 0;
        for (float v : x) { if (std::fabs(v - c0) <= std::fabs(v - c1)) { s0 += v; n0++; } else { s1 += v; n1++; } }
        if (n0) c0 = (float)(s0 / n0);
        if (n1) c1 = (float)(s1 / n1);
    }
    return c1 > c0;
}

} // namespace

void SoftDecoder::estimate(float prior_dit) {
    std::vector<float> marks, gaps;
    for (const Iv &v : hist_) (v.mark ? marks : gaps).push_back(v.ms);
    Params q;
    q.dit = prior_dit > 0 ? prior_dit : 60.0f; q.dah = 3.0f * q.dit;
    if (marks.size() >= 6) {
        float c0, c1;
        if (two_means(marks, c0, c1) && c1 / c0 > 1.7f) { q.dit = c0; q.dah = c1; }
        else {
            std::sort(marks.begin(), marks.end()); float med = marks[marks.size() / 2];
            if (med < 1.5f * q.dit) { q.dit = med; q.dah = 3.0f * med; } else { q.dah = med; q.dit = med / 3.0f; }
        }
    }
    q.eg = q.dit;
    if (gaps.size() >= 6) {
        std::vector<float> lg; for (float g : gaps) lg.push_back(std::log(g));
        float a, b;
        if (two_means(lg, a, b)) q.eg = std::min(std::max(std::exp(a), 0.6f * q.dit), 1.4f * q.dit);
    }
    q.cg = 3.0f * q.dit; q.wg = 7.0f * q.dit;
    std::vector<float> longg; for (float g : gaps) if (g > 2.0f * q.dit) longg.push_back(g);
    if (longg.size() >= 5) {
        std::vector<float> lg; for (float g : longg) lg.push_back(std::log(g));
        float a, b;
        std::sort(longg.begin(), longg.end()); float med = longg[longg.size() / 2];
        if (two_means(lg, a, b) && std::exp(b) / std::exp(a) > 1.6f) { q.cg = std::exp(a); q.wg = std::exp(b); }
        else if (med < 5.0f * q.dit) { q.cg = std::min(med, 3.5f * q.dit); q.wg = 7.0f * q.dit; }
        else { q.cg = 3.0f * q.dit; q.wg = std::max(med, 5.5f * q.dit); }
    }
    /* the operator's own spread: residuals of every mark/gap against its nearest centre (log domain) */
    {
        double sm = 0; int nm = 0, ng = 0; double sg = 0;
        for (const Iv &v : hist_) {
            if (v.mark) { float r = std::min(std::fabs(std::log(v.ms / q.dit)), std::fabs(std::log(v.ms / q.dah))); sm += r * r; nm++; }
            else { float r = std::min({std::fabs(std::log(v.ms / q.eg)), std::fabs(std::log(v.ms / q.cg)), std::fabs(std::log(v.ms / q.wg))}); sg += r * r; ng++; }
        }
        if (nm >= 10) q.sd_m = std::min(std::max((float)std::sqrt(sm / nm) * 1.15f, SD_MIN), SD_MAX);
        if (ng >= 10) q.sd_g = std::min(std::max((float)std::sqrt(sg / ng) * 1.25f, SD_MIN), SD_MAX);
    }
    p_ = q;
}

void SoftDecoder::emit(const std::string &s) {
    if (s.empty() || !out_) return;
    for (size_t i = 0; i < s.size();) {
        if (s[i] == ' ') { if (!last_space_) out_(" ", false); last_space_ = true; i++; continue; }
        size_t j = s[i] == '<' ? s.find('>', i) : i;
        if (j == std::string::npos) j = i;
        std::string tok = s.substr(i, j - i + 1);
        out_(tok.c_str(), false); last_space_ = false; i = j + 1;
    }
}

/* Beam search over the pending word. State = (partial code of the character in progress, last emitted character). */
namespace {
float LM_W = 0.5f;
int lm_index(char ch) { const char *p = std::strchr(LM_ALPHA, ch); return (ch && p) ? (int)(p - LM_ALPHA) : -1; }
/* log P(next | last) from the bigram table; symbols outside the table (punctuation, prosigns) get a flat penalty */
float bigram(char last, const char *sym) {
    if (sym[0] && !sym[1]) { int a = lm_index(last), b = lm_index(sym[0]); if (a >= 0 && b >= 0) return LM_W * LM_BI[a][b]; }
    return std::log(0.002f);
}
}

void SoftDecoder::decode_pending(bool final_is_word) {
    if (pending_.empty()) return;
    if (const char *w = std::getenv("CW_LMW")) LM_W = (float)std::atof(w);
    struct St { float score; std::string text; };
    using Key = std::pair<std::string, char>;
    std::map<Key, St> cur; cur[{"", ' '}] = {0.0f, ""};
    const Params &q = p_;
    for (size_t k = 0; k < pending_.size(); k++) {
        const Iv &v = pending_[k];
        std::map<Key, St> nxt;
        auto put = [&](const std::string &code, char last, float sc, const std::string &txt) {
            auto it = nxt.find({code, last});
            if (it == nxt.end() || it->second.score < sc) nxt[{code, last}] = {sc, txt};
        };
        for (auto &kv : cur) {
            const std::string &code = kv.first.first; char last = kv.first.second; float sc = kv.second.score; const std::string &txt = kv.second.text;
            if (v.mark) {
                if (code.size() < 7) { put(code + ".", last, sc + ll(v.ms, q.dit, q.sd_m), txt); put(code + "-", last, sc + ll(v.ms, q.dah, q.sd_m), txt); }
            } else {
                const char *t = code.empty() ? nullptr : morse_to_text(code.c_str());
                float lp = code.empty() ? 0.0f : (t ? bigram(last, t) : INVALID);
                char nl = (t && t[0] && !t[1]) ? t[0] : ' ';
                std::string out = txt + (code.empty() ? "" : (t ? t : "<?>"));
                if (!code.empty()) {
                    put(code, last, sc + ll(v.ms, q.eg, q.sd_g) + std::log(0.55f), txt);
                    put("", nl, sc + ll(v.ms, q.cg, q.sd_g) + std::log(0.30f) + lp, out);
                }
                /* word gap: the character ends, then a space follows it (P(space | last char)) */
                float sp = bigram(nl, " ");
                put("", ' ', sc + ll(v.ms, q.wg, q.sd_g) + std::log(0.15f) + lp + sp, out + " ");
            }
        }
        if (nxt.size() > BEAM) {
            std::vector<std::pair<float, Key>> v2; for (auto &kv : nxt) v2.push_back({kv.second.score, kv.first});
            std::partial_sort(v2.begin(), v2.begin() + BEAM, v2.end(), [](auto &a, auto &b) { return a.first > b.first; });
            std::map<Key, St> keep; for (size_t i = 0; i < BEAM; i++) keep[v2[i].second] = nxt[v2[i].second];
            nxt.swap(keep);
        }
        cur.swap(nxt);
    }
    float best = -1e30f; std::string out;
    for (auto &kv : cur) {
        const std::string &code = kv.first.first; char last = kv.first.second; float sc = kv.second.score; std::string txt = kv.second.text;
        if (!final_is_word && !code.empty()) continue;   /* forced cut: end only on a decided character boundary */
        if (!code.empty()) { const char *t = morse_to_text(code.c_str()); sc += t ? bigram(last, t) : INVALID; txt += t ? t : "<?>"; }
        if (final_is_word) sc += bigram(txt.empty() ? ' ' : txt.back(), " ");
        if (sc > best) { best = sc; out = txt; }
    }
    if (final_is_word && !out.empty() && out.back() != ' ') out += ' ';
    if (std::getenv("CW_DEBUG")) { fprintf(stderr, "[dit %.0f dah %.0f eg %.0f cg %.0f wg %.0f sd %.2f/%.2f] => '%s'\n", q.dit, q.dah, q.eg, q.cg, q.wg, q.sd_m, q.sd_g, out.c_str()); }
    emit(out);
    pending_.clear();
}

void SoftDecoder::interval(bool mark, float ms, bool strong, float prior_dit) {
    if (std::getenv("CW_TRACE")) fprintf(stderr, "IV %c %.1f\n", mark ? 'M' : 'g', ms);
    if (mark) {
        float dit = p_.dit > 0 ? p_.dit : prior_dit;
        if (ms < BLIP_K * dit) {                     /* noise blip: swallow it and merge the gaps around it */
            if (!pending_.empty() && !pending_.back().mark) { carry_gap_ = pending_.back().ms + ms; pending_.pop_back(); }
            else carry_gap_ += ms;
            return;
        }
        if (ms > 3.0f * p_.dah) { pending_.clear(); flushed_ = true; carry_gap_ = 0; return; }   /* a carrier */
        if (pending_.empty() && !strong && ms < 2.5f * dit) return;   /* a weak lone blip does not open a word */
        if (carry_gap_ > 0) { if (!pending_.empty() && !pending_.back().mark) pending_.back().ms += carry_gap_; carry_gap_ = 0; }
        pending_.push_back({true, ms}); hist_.push_back({true, ms}); flushed_ = false;
    } else {
        if (pending_.empty()) { carry_gap_ = 0; return; }       /* gap before any accepted mark */
        float g = ms + carry_gap_; carry_gap_ = 0;
        if (flushed_) return;                                  /* word already ended by idle(): this gap was its end */
        pending_.push_back({false, g}); hist_.push_back({false, g});
        if (pending_.size() >= PEND_MAX) { estimate(prior_dit); decode_pending(false); }
    }
    if (hist_.size() > HIST_MAX) hist_.erase(hist_.begin(), hist_.begin() + (hist_.size() - HIST_MAX));
}

void SoftDecoder::idle(float gap_ms, float prior_dit) {
    if (flushed_ || pending_.empty() || pending_.back().mark == false) return;
    estimate(prior_dit);
    float trig = std::max(std::sqrt(p_.cg * p_.wg), 4.0f * p_.dit);
    if (gap_ms >= trig) { decode_pending(true); flushed_ = true; }
}

} // namespace cw
