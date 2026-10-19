#!/usr/bin/env python
import inkex
import random
import math
from inkex import Transform

class SimplexNoise:
    def __init__(self, seed=42):
        rng = random.Random(seed)
        self.p = list(range(256))
        rng.shuffle(self.p)
        self.perm = self.p * 2
        self.grad3 = [
            (1,1), (-1,1), (1,-1), (-1,-1),
            (1,0), (-1,0), (0,1), (0,-1)
        ]
        self.F2 = 0.5 * (math.sqrt(3.0) - 1.0)
        self.G2 = (3.0 - math.sqrt(3.0)) / 6.0

    def _dot(self, g, x, y):
        return g[0]*x + g[1]*y

    def noise2d(self, xin, yin):
        s = (xin + yin) * self.F2
        i = math.floor(xin + s)
        j = math.floor(yin + s)
        t = (i + j) * self.G2
        X0 = i - t
        Y0 = j - t
        x0 = xin - X0
        y0 = yin - Y0

        if x0 > y0:
            i1, j1 = 1, 0
        else:
            i1, j1 = 0, 1

        x1 = x0 - i1 + self.G2
        y1 = y0 - j1 + self.G2
        x2 = x0 - 1.0 + 2.0 * self.G2
        y2 = y0 - 1.0 + 2.0 * self.G2

        ii = int(i) & 255
        jj = int(j) & 255
        gi0 = self.perm[ii + self.perm[jj]] % 8
        gi1 = self.perm[ii + i1 + self.perm[jj + j1]] % 8
        gi2 = self.perm[ii + 1 + self.perm[jj + 1]] % 8

        n0 = n1 = n2 = 0.0
        t0 = 0.5 - x0*x0 - y0*y0
        if t0 > 0:
            t0 *= t0
            n0 = t0 * t0 * self._dot(self.grad3[gi0], x0, y0)
        t1 = 0.5 - x1*x1 - y1*y1
        if t1 > 0:
            t1 *= t1
            n1 = t1 * t1 * self._dot(self.grad3[gi1], x1, y1)
        t2 = 0.5 - x2*x2 - y2*y2
        if t2 > 0:
            t2 *= t2
            n2 = t2 * t2 * self._dot(self.grad3[gi2], x2, y2)

        return 70.0 * (n0 + n1 + n2)


class NoiseTiling(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--width", type=float, default=300)
        pars.add_argument("--height", type=float, default=300)
        pars.add_argument("--scale_noise", type=float, default=0.02)
        pars.add_argument("--threshold", type=float, default=0.3)
        pars.add_argument("--seed", type=int, default=0)
        pars.add_argument("--attempts", type=int, default=500)
        pars.add_argument("--min_scale", type=float, default=0.6)
        pars.add_argument("--max_scale", type=float, default=1.4)
        pars.add_argument("--min_rotate", type=float, default=0.0)
        pars.add_argument("--max_rotate", type=float, default=360.0)
        pars.add_argument("--padding", type=float, default=2)

    def effect(self):
        if not self.svg.selected:
            inkex.errormsg("Please select one or more objects to use as templates.")
            return

        selected_objs = list(self.svg.selected.values())

        try:
            anchor_bbox = selected_objs[0].bounding_box()
        except Exception:
            inkex.errormsg("Could not determine the bounding box of the selected object.")
            return

        area_x = anchor_bbox.left
        area_y = anchor_bbox.top
        area_w = self.options.width
        area_h = self.options.height

        if self.options.seed and self.options.seed > 0:
            noise_seed = self.options.seed
        else:
            noise_seed = random.randint(0, 2147483647)
        noise_gen = SimplexNoise(seed=noise_seed)
        rng = random.Random(noise_seed)

        placed_bboxes = []

        attempts = 0
        max_attempts = self.options.attempts
        placed_count = 0

        while attempts < max_attempts:
            attempts += 1

            cand_x = area_x + random.random() * area_w
            cand_y = area_y + random.random() * area_h

            n_val = noise_gen.noise2d(cand_x * self.options.scale_noise,
                                      cand_y * self.options.scale_noise)
            probability = (n_val + 1.0) / 2.0

            if probability < self.options.threshold:
                continue
            if random.random() > probability:
                continue

            template = random.choice(selected_objs)

            try:
                orig_bbox = template.bounding_box()
                orig_w = orig_bbox.width
                orig_h = orig_bbox.height
                if orig_w == 0 or orig_h == 0:
                    continue
            except Exception:
                continue

            rand_scale = rng.uniform(self.options.min_scale, self.options.max_scale)
            r_min = min(self.options.min_rotate, self.options.max_rotate)
            r_max = max(self.options.min_rotate, self.options.max_rotate)
            rand_rotation = rng.uniform(r_min, r_max)

            diag = math.sqrt(orig_w**2 + orig_h**2)
            half_size = (diag * rand_scale) / 2.0

            cand_bbox = (
                cand_x - half_size,
                cand_y - half_size,
                cand_x + half_size,
                cand_y + half_size
            )

            collision = False
            pad = self.options.padding
            for (bx1, by1, bx2, by2) in placed_bboxes:
                if not (cand_bbox[2] + pad < bx1 or
                        cand_bbox[0] - pad > bx2 or
                        cand_bbox[3] + pad < by1 or
                        cand_bbox[1] - pad > by2):
                    collision = True
                    break

            if collision:
                continue

            orig_cx = (orig_bbox.left + orig_bbox.right) / 2.0
            orig_cy = (orig_bbox.top + orig_bbox.bottom) / 2.0

            tr = Transform()
            tr.add_translate(cand_x, cand_y)
            tr.add_rotate(rand_rotation)
            tr.add_scale(rand_scale)
            tr.add_translate(-orig_cx, -orig_cy)

            new_elem = template.duplicate()
            new_elem.set('id', self.svg.get_unique_id('tile'))
            
            if new_elem.get('transform'):
                new_elem.set('transform', str(tr) + " " + new_elem.get('transform'))
            else:
                new_elem.set('transform', str(tr))

            placed_bboxes.append(cand_bbox)
            placed_count += 1


if __name__ == '__main__':
    NoiseTiling().run()