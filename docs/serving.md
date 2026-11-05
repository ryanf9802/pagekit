# Serving pages

Serving is optional. Every command works with the server down, and a built page is a plain file. The server adds
an index of your pages, the **Download PDF** button, and links you can open from elsewhere.

## The page index

```bash
pagekit serve               # runs on http://localhost:8766 until the terminal closes
pagekit install-service     # or always on, as a systemd user service
```

Set `PAGEKIT_PORT` or pass `--port` to use another port. The server listens on localhost only. Served pages show
an **All pages** link in the header, back to the index. Packed and saved copies have no index, so they have no
link, and it does not print.

## Starting at login

`install-service` needs systemd, which covers most Linux systems and WSL with systemd enabled. Elsewhere, have the
operating system run `pagekit serve` at login:

- **Windows:** create a scheduled task, using the full path that `where pagekit` prints:

  ```text
  schtasks /Create /TN pagekit /SC ONLOGON /TR "C:\path\to\pagekit.exe serve"
  ```

- **macOS:** add a launchd agent in `~/Library/LaunchAgents/` that runs `pagekit serve`, with `RunAtLoad` set.

## Over SSH

Forward the port from the machine you are connecting from, in its `~/.ssh/config`:

```text
LocalForward 8766 localhost:8766
```

If you use connection sharing, restart the shared master so the change applies: `ssh -O exit HOST`.

## From your other devices

To open pages from your other devices, put the server behind a private network address and tell pagekit. With
[Tailscale](https://tailscale.com), for example:

```bash
tailscale serve --bg 8766
pagekit install-service --public-url https://HOST.TAILNET.ts.net
```

The server then accepts that one extra name, and builds print that address as the page link. Keep the address
private: avoid anything that exposes it to the public internet, such as `tailscale funnel`. Each device needs
access to that network.

## On a phone

Pages are built for phones, and the index can be added to a home screen as an app, using the browser menu's
**Add to Home screen**. This needs the https address above.
