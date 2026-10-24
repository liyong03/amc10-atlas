"""Pass C: deterministic keyword/regex classifier, used as an independent cross-check
of the two LLM passes. Writes data/<contest>/labels/passC.json with the top-scoring categories."""
import json, os, re

from contest import D

# category id -> list of (regex, weight). Matched case-insensitively against problem text.
RULES = {
    'alg-custom-op': [(r'\\(diamond|star|clubsuit|heartsuit|spadesuit|otimes|oplus|ast|bowtie|spadesuit|blacktriangle)', 3), (r'is defined (as|by|to be)', 1.5), (r'for all (real )?numbers? \$?a\$? and \$?b', 1.5)],
    'alg-linear-word': [(r'\b(years? old|age)\b', 2), (r'\bcoins?\b|\bnickels?\b|\bdimes?\b|\bquarters\b', 1.5), (r'\bweigh', 1)],
    'alg-systems': [(r'\\begin\{(align|cases)', 1.5), (r'system of equations', 3), (r'\$[^$]*=[^$]*\$[^$]*and[^$]*\$[^$]*=[^$]*\$', 0.8)],
    'alg-rates': [(r'miles per hour|mph|km/h|kilometers per hour|feet per second|meters per (second|minute)|speed', 3), (r'\b(drives?|bikes?|walks?|runs?|jogs?|rides?|travels?)\b', 1), (r'\bminutes?\b', 0.5)],
    'alg-work': [(r'\bpaint(s|ing)?\b.*\b(hours?|minutes?)\b', 2), (r'\b(fill|empty|drain)s?\b.*\b(tank|pool|pipe)', 3), (r'working together|working alone|at (their|the same) (constant )?rates?', 3)],
    'alg-percent-ratio': [(r'\\%|percent', 3), (r'\bratio\b', 2.5), (r'\bdiscount|\bsale\b|\bincreased? by\b|\bdecreased? by\b', 1.5), (r'\bmixture|solution is .* acid|alcohol', 2)],
    'alg-mean-median': [(r'\b(average|mean|arithmetic mean)\b', 3), (r'\bmedian\b', 3), (r'\bmode\b', 2), (r'\brange\b', 1)],
    'alg-exponents-radicals': [(r'\\sqrt', 1.5), (r'\^\{?\d{2,}|\^\{[a-z]', 1), (r'\\sqrt\[', 1.5)],
    'alg-logs': [(r'\\log', 4)],
    'alg-factoring-identities': [(r'\bsimplif', 1), (r'\\frac\{1\}\{[a-z]\}', 1.5), (r'x\s*\+\s*\\frac\s*\{?1\}?\s*\{?x', 2)],
    'alg-quadratics': [(r'x\^2', 1.5), (r'\broots?\b', 1.5), (r'quadratic', 3), (r'parabola', 2), (r'discriminant', 3)],
    'alg-polynomials': [(r'polynomial', 3), (r'x\^\{?[3-9]', 2), (r'\bcubic\b', 2)],
    'alg-functions': [(r'\bf\(', 2), (r'\bfunction\b', 2), (r'f\(f\(', 3), (r'g\(', 1)],
    'alg-graphs-lines': [(r'\bslope\b', 3), (r'\b[xy]-intercept', 3), (r'\blines?\b.*\bintersect', 1.5), (r'y\s*=\s*-?\d*\s*x\s*[+-]', 1.5)],
    'alg-inequalities-optimization': [(r'\b(largest|greatest|maximum|smallest|minimum|least) possible value\b', 2), (r'\\le|\\ge|\\leq|\\geq|<|>', 0.5), (r'\binequalit', 2)],
    'alg-absolute-value': [(r'\|[^|$]+\|', 2.5), (r'\\lvert|\\left\|', 2.5), (r'absolute value', 3)],
    'alg-floor-ceiling': [(r'\\lfloor|\\lceil', 4), (r'greatest integer', 3), (r'\brounds?\b|\brounded\b', 1.5)],
    'alg-arith-seq': [(r'arithmetic (sequence|progression|series)', 4), (r'1\s*\+\s*2\s*\+\s*3\s*\+\s*\\(c|l)dots', 2), (r'common difference', 3)],
    'alg-geom-seq': [(r'geometric (sequence|progression|series)', 4), (r'common ratio', 3), (r'infinite (series|sum)', 2)],
    'alg-recursion-patterns': [(r'\ba_\{?n', 2), (r'\bsequence\b', 1.5), (r'\b(20\d\d)(st|nd|rd|th) term\b', 3), (r'pattern', 1.5), (r'\bterm\b', 1)],
    'alg-complex': [(r'\bi\^\{?\d|\bimaginary|complex number|\\overline\{z\}|\bz\s*=', 3)],
    'alg-trig': [(r'\\(sin|cos|tan)\b', 3)],
    'alg-arith-compute': [(r'^\s*what is (the value of )?\$[^$]*\$\s*\?', 3), (r'^\s*\$[^$]*\$\s*(equals|=)', 2), (r'\bvalue of\b', 0.5)],

    'nt-divisibility': [(r'divisible by', 3), (r'\bmultiples? of\b', 2), (r'\bdivides\b', 2)],
    'nt-divisors': [(r'\b(positive )?(divisors?|factors)\b', 2.5), (r'number of (positive )?(integer )?divisors', 3)],
    'nt-primes-factorization': [(r'\bprimes?\b', 3), (r'prime factori', 3)],
    'nt-gcd-lcm': [(r'greatest common (divisor|factor)|\\gcd|\bgcd\b', 4), (r'least common multiple|\\operatorname\{lcm\}|\blcm\b', 4)],
    'nt-modular': [(r'\bremainder\b', 3.5), (r'\\pmod|\\mod|\bmod\b', 3.5)],
    'nt-units-digit': [(r'units digit|ones digit|last (two )?digits?|tens digit', 4)],
    'nt-digits': [(r'\bdigits?\b', 2), (r'palindrome', 3), (r'sum of (the|its) digits', 2)],
    'nt-bases': [(r'base[- ]\$?\d|_\{?\d\}?\b.*base|\bbase\b', 3.5)],
    'nt-diophantine': [(r'ordered pairs of (positive )?integers', 3), (r'integer solutions', 3), (r'positive integers \$[a-z]\$ and \$[a-z]\$', 1.5)],
    'nt-factorials': [(r'!', 1.5), (r'factorial', 3), (r'trailing zeros|ends? in .* zeros', 4)],
    'nt-squares-cubes': [(r'perfect (square|cube|power)', 3.5)],
    'nt-fractions-decimals': [(r'repeating decimal|\\overline\{\d', 3.5), (r'lowest terms|relatively prime positive integers', 1), (r'decimal', 1.5)],
    'nt-parity': [(r'\b(odd|even)\b', 2), (r'consecutive (positive )?(odd |even )?integers', 2)],

    'cp-basic-counting': [(r'\bhow many (different |distinct )?(ways|possible|numbers|integers)\b', 2), (r'\bhow many\b', 0.8)],
    'cp-permutations': [(r'\barrange|\barrangements?\b|\border(s|ed|ing)?\b', 2), (r'\b(line|row) up\b|in a (row|line)', 1.5), (r'\bseat(s|ed|ing)?\b', 2)],
    'cp-combinations': [(r'\bchoose|\bchosen\b|\bselect(ed|ion)?\b|committee|subsets?', 2.5), (r'\\binom', 3), (r'handshake|shakes hands', 3)],
    'cp-distributions': [(r'\bdistribut', 3), (r'identical (balls|candies|objects|coins)', 3)],
    'cp-inclusion-exclusion': [(r'\bboth\b', 1.5), (r'\bneither\b', 2.5), (r'venn', 4), (r'\bat least one\b', 1)],
    'cp-paths-grids': [(r'\bpaths?\b|\broutes?\b', 2.5), (r'\bgrid\b', 1.5), (r'lattice', 1.5), (r'how many (rectangles|squares|triangles)', 2)],
    'cp-recursion-counting': [(r'no two (consecutive|adjacent)', 3), (r'\bsteps? (at a time|or)', 2), (r'\btil(e|ing)s?\b', 1.5)],
    'cp-probability-basic': [(r'\bprobability\b', 2.5), (r'\bat random\b|\brandomly\b', 1.5)],
    'cp-probability-dice-coins': [(r'\bdice\b|\bdie\b|\bcoins? (is |are )?(flipped|tossed)|\bflip', 3), (r'\bspinner', 3)],
    'cp-geometric-probability': [(r'(point|number)s? .*(chosen|selected) .*(at random|randomly).*(interval|inside|interior|region|square|from the)', 3), (r'real number.*at random|at random.*real number', 3)],
    'cp-expected-value': [(r'expected (value|number)', 4), (r'on average', 1.5)],
    'cp-conditional-probability': [(r'\bgiven that\b', 2.5), (r'\bprobability\b.*\b(wins?|game|turn|round)\b', 1.5)],
    'cp-pigeonhole': [(r'\bguarantee', 4), (r'\bmust (be )?(drawn|selected|chosen|pick)', 2.5), (r'minimum number .* to (ensure|be sure)', 3)],

    'geo-angles': [(r'\\angle|\bangles?\b|\^\\circ|\^\{\\circ\}|degrees', 2)],
    'geo-triangle-area': [(r'\btriangle\b', 1.5), (r'\barea\b', 1)],
    'geo-pythagorean': [(r'right (triangle|angle)', 2.5), (r'hypotenuse|\blegs?\b', 2), (r'\\angle [A-Z]{3}\s*=\s*90', 2)],
    'geo-similar': [(r'\bsimilar\b', 3), (r'\bparallel\b', 1.5), (r'\\parallel', 1.5)],
    'geo-triangle-centers': [(r'incircle|inscribed in (the )?triangle|circumcircle|circumscribed|inradius|circumradius|centroid|orthocenter|\bmedians?\b', 3)],
    'geo-triangle-inequality': [(r'(non-?degenerate|scalene|integer side|side lengths are (distinct )?(positive )?integers)', 2.5), (r'\bperimeter\b.*\btriangles?\b', 1.5)],
    'geo-quadrilaterals': [(r'\b(rectangle|square|trapezoid|parallelogram|rhombus|kite|quadrilateral)\b', 2)],
    'geo-polygons': [(r'\b(regular )?(hexagon|octagon|pentagon|polygon|dodecagon|decagon|nonagon|heptagon)', 3)],
    'geo-circle-area': [(r'\bcircles?\b|\bradius\b|\bdiameter\b|\bsemicircle|\bsector|\barc\b', 1.5), (r'\\pi', 1.5)],
    'geo-circle-theorems': [(r'\btangent\b', 2.5), (r'\bchords?\b', 2.5), (r'inscribed (in|angle)', 1.5)],
    'geo-shaded-regions': [(r'\bshaded\b', 3.5), (r'\b(overlap|region)\b', 1)],
    'geo-coordinate': [(r'\(\s*-?\d+\s*,\s*-?\d+\s*\)', 2.5), (r'coordinate|\bxy-plane|\bplane\b', 2), (r'lattice points?', 1.5)],
    'geo-graph-regions': [(r'graphs? of', 2.5), (r'region .* (satisfying|bounded|enclosed)|bounded by', 2.5), (r'\|x\|', 2)],
    'geo-transformations': [(r'reflect|rotat|fold|translat|symmetr', 3)],
    'geo-3d-volume': [(r'\bvolume\b', 3), (r'surface area', 3), (r'\b(cylinder|cone|sphere|pyramid|prism|tetrahedron)', 2.5)],
    'geo-3d-cubes': [(r'\bcubes?\b', 2.5), (r'\bfaces?\b|\bvertices\b|\bedges\b', 1), (r'\bnet\b|unit cubes|painted', 2)],
    'geo-trig': [(r'\\(sin|cos|tan)', 2)],
    'geo-perimeter-length': [(r'\bperimeter\b', 2.5), (r'\blength of\b', 1)],

    'misc-logic': [(r'\b(lie|lies|liar|truth|always tells|statements?)\b', 2.5), (r'\bwho\b.*\?', 1), (r'must be true|cannot be', 1.5)],
    'misc-games': [(r'\bgame\b|\bplayers?\b|\bturns?\b|\bwinning strategy', 2)],
    'misc-calendar-clock': [(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 3), (r'\bclock\b|\bo\'clock\b|\b\d{1,2}:\d{2}\b|\b(a\.m\.|p\.m\.)', 2.5), (r'\bcalendar|\bleap year', 3)],
    'misc-data-charts': [(r'\b(graph|chart|table|histogram) (shows|below|above|at right)', 3), (r'\bbar graph|pie chart|line graph', 3)],
    'misc-money-everyday': [(r'\$\\\$|\\\$\d|dollars?|cents?', 2), (r'\b(buy|bought|costs?|price|pays?|paid|sells?|sold|tip)\b', 1)],
    'misc-process-simulation': [(r'\brepeat(s|ed|edly)?\b|\bprocess\b|\bprocedure\b|\balgorithm', 2), (r'\btournament|\bteams?\b|\bplay(s|ed)? (each|every)', 1.5)],
    'misc-magic-squares': [(r'magic square', 4), (r'\beach of the (numbers|digits|integers)\b.*\b(placed|written|used)', 2), (r'\bsums? (along|of the numbers in) each', 2.5)],

    # AMC 8 only
    'alg-fraction-word': [(r'\\(d|t)?frac\{1\}\{[2-9]\}\$? of (the|her|his|their|all)', 2.5), (r'\b(half|third|quarter|fourth|fifth) of (the|her|his|their|what)', 2.5), (r'\b(remaining|rest|left over|what was left)\b', 1.5)],
    'alg-visual-patterns': [(r'toothpicks?|matchsticks?', 3), (r'\b(figure|stage|step)s? \$?\d+\$?\b.*\b(figure|stage|step)s? \$?\d+', 2), (r'pattern (continues|shown)', 2.5)],
    'geo-grid-area': [(r'\b(grid|dot paper|geoboard|unit squares?)\b', 2), (r'\bcut\b.*\b(pieces|rearrang)', 2.5)],
    'misc-units-measurement': [(r'\b(inch(es)?|feet|foot|yards?|miles?|ounces?|pounds?|cups?|quarts?|gallons?|liters?|centimeters?|meters?)\b.*\bin (a|an|one)\b', 2.5), (r'\bscale\b|\bmap\b', 2.5), (r'\bconver', 2)],
}


def classify(text):
    t = text.split('$\\textbf{(A)')[0]  # ignore the answer-choice line
    scores = {}
    for cat, rules in RULES.items():
        s = 0.0
        for pat, w in rules:
            if re.search(pat, t, flags=re.IGNORECASE):
                s += w
        if s:
            scores[cat] = s
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return [c for c, _ in ranked[:3]], dict(ranked[:5])


def main():
    problems = json.load(open(D('problems.json')))
    valid = {c['id'] for c in json.load(open(D('taxonomy.json')))['categories']}
    for cat in set(RULES) - valid:  # rules for topics this contest's taxonomy doesn't have
        del RULES[cat]
    out = []
    for p in problems:
        top, scores = classify(p['text'])
        out.append({'id': p['id'], 'top': top, 'scores': scores})
    os.makedirs(D('labels'), exist_ok=True)
    json.dump(out, open(D('labels/passC.json'), 'w'), indent=1)
    print('classified', len(out), '| no match:', sum(1 for o in out if not o['top']))


if __name__ == '__main__':
    main()
