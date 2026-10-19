import type { ErrorEvent, EventHint } from "@sentry/nextjs";
import { describe, expect, it } from "vitest";

import { beforeSend, scrubString, sentryOptions } from "@/lib/sentry";

describe("sentryOptions", () => {
  it.each([undefined, ""])("skips Sentry when the DSN is %j", (dsn) => {
    expect(sentryOptions({ dsn, environment: undefined, vercelEnv: undefined })).toBeNull();
  });

  it("never sends default PII and picks the environment", () => {
    const dsn = "https://key@o1.ingest.de.sentry.io/1";
    expect(sentryOptions({ dsn, environment: undefined, vercelEnv: "preview" })).toMatchObject({
      dsn,
      environment: "preview",
      sendDefaultPii: false,
    });
    expect(sentryOptions({ dsn, environment: "staging", vercelEnv: "preview" })?.environment).toBe(
      "staging",
    );
    expect(sentryOptions({ dsn, environment: undefined, vercelEnv: undefined })?.environment).toBe(
      "development",
    );
  });
});

describe("scrubString", () => {
  it.each([
    ["email", "no user rider@example.com", "no user [email]"],
    ["JWT", "bearer eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "bearer [jwt]"],
    [
      "signed storage URL",
      "http://127.0.0.1:54321/storage/v1/object/sign/insoles/u1/a.jpg?token=abc",
      "http://127.0.0.1:54321/storage/v1/object/sign/[Filtered]?token=[Filtered]",
    ],
    [
      "magic-link query",
      "/auth/callback?token_hash=xyz&type=email",
      "/auth/callback?token_hash=[Filtered]&type=[Filtered]",
    ],
  ])("scrubs %s", (_label, input, expected) => {
    expect(scrubString(input)).toBe(expected);
  });
});

describe("beforeSend", () => {
  it("removes bodies, cookies, auth headers, user details and attachments", () => {
    const event: ErrorEvent = {
      type: undefined,
      message: "upload failed for rider@example.com",
      user: { id: "u1", email: "rider@example.com", ip_address: "1.2.3.4" },
      request: {
        url: "https://fitfinder.app/submissions?code=secret",
        query_string: "code=secret&type=email",
        data: { image: "base64..." },
        cookies: { "sb-abc-auth-token": "eyJx.eyJy.z" },
        headers: {
          Cookie: "sb-abc-auth-token=1",
          Authorization: "Bearer 1",
          apikey: "sb_publishable_1",
          Referer: "https://fitfinder.app/login?email=a",
          "User-Agent": "Firefox",
        },
      },
      breadcrumbs: [{ data: { url: "/storage/v1/object/sign/insoles/u1/a.jpg?token=t" } }],
      extra: { accessToken: "abc", count: 2 },
    };
    const hint: EventHint = { attachments: [{ filename: "insole.jpg", data: "..." }] };

    const result = beforeSend(event, hint);

    expect(result.message).toBe("upload failed for [email]");
    expect(result.user).toEqual({ id: "u1" });
    expect(result.request).toEqual({
      url: "https://fitfinder.app/submissions?code=[Filtered]",
      headers: { "User-Agent": "Firefox" },
    });
    expect(result.breadcrumbs?.[0].data?.url).toBe(
      "/storage/v1/object/sign/[Filtered]?token=[Filtered]",
    );
    expect(result.extra).toEqual({ accessToken: "[Filtered]", count: 2 });
    expect(hint.attachments).toHaveLength(0);
  });
});
