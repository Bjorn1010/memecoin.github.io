"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";

/* Newsletter.
 *
 * Deliberately not a white strip with an input in it: this is a full section
 * with its own type treatment, so it reads as part of the page rather than
 * as a plugin dropped into the footer. Same void background as everywhere
 * else — the floodlight wash is what gives it its own weight, not colour.
 *
 * There is no mailing list wired up, so the success state says so rather than
 * claiming a subscription that will never arrive. */
export function Newsletter() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "invalid" | "done">("idle");

  return (
    <section className="relative isolate overflow-hidden border-y border-line bg-void">
      <div aria-hidden className="floodlight absolute inset-0 -z-10" />
      <div className="mx-auto grid max-w-[1600px] gap-10 px-5 py-20 lg:grid-cols-2 lg:items-center lg:px-10 lg:py-28">
        <div>
          <p className="eyebrow label-mono mb-5">Newsletter</p>
          <h2 className="font-display text-display text-ink">
            Restez
            <br />
            dans le jeu.
          </h2>
          <p className="mt-6 max-w-md text-base leading-relaxed text-steel-200">
            Les nouveaux maillots, les rééditions, et les tailles qui reviennent en stock. Rien
            d&apos;autre.
          </p>
        </div>

        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            /* Validated here rather than left to the browser so the message
               matches the rest of the page's voice and stays in French. */
            const ok = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim());
            setState(ok ? "done" : "invalid");
            if (ok) setEmail("");
          }}
          className="lg:justify-self-end lg:pl-10"
        >
          <label htmlFor="newsletter-email" className="label-mono mb-3 block text-steel-300">
            Adresse email
          </label>
          <div className="flex max-w-md gap-2">
            <input
              id="newsletter-email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (state !== "idle") setState("idle");
              }}
              placeholder="vous@exemple.com"
              aria-invalid={state === "invalid"}
              aria-describedby="newsletter-msg"
              className="min-w-0 flex-1 border border-ink/25 bg-void/40 px-4 py-4 text-sm text-ink placeholder:text-steel-500 focus:border-volt focus:outline-none"
            />
            <button
              type="submit"
              className="group inline-flex shrink-0 items-center gap-2 bg-ink px-6 py-4 font-display text-sm uppercase tracking-wide text-void transition-colors hover:bg-volt hover:text-on-volt"
            >
              Rejoindre
              <ArrowRight size={16} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
            </button>
          </div>
          <p
            id="newsletter-msg"
            role="status"
            className="mt-3 min-h-[1.25rem] text-xs text-steel-300"
          >
            {state === "invalid" && "Cette adresse email n'est pas valide."}
            {state === "done" &&
              "Adresse enregistrée côté interface. Aucune liste de diffusion n'est encore connectée à ce formulaire."}
          </p>
        </form>
      </div>
    </section>
  );
}
