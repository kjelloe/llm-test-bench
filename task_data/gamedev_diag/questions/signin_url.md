# signin_url

A licence sign-in URL printed by a CLI in a narrow terminal was copied into a browser and failed with `invalid client_id`. Opening the same flow again and copying carefully failed the same way. Why, and what is the fix?

A. The client_id expires 60 seconds after it is printed; finish the whole sign-in within a minute of starting it.
B. The URL is printed URL-encoded twice; decode it once before pasting it into the browser.
C. The browser blocks the redirect to localhost; allow localhost redirects in its site settings and try again.
D. The terminal's line wrap put a space into the copied URL; open the URL programmatically instead of copying it.
E. The terminal converts `&` to `&amp;` when copying; replace the entities before pasting.
