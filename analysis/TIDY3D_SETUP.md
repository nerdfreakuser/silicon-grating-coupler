# Tidy3D API key (do this once)

The Python client is already installed (`tidy3d 2.12.0`). Simulations run on Flexcompute’s cloud, so the client needs an API key. **Do not paste the key into this chat.** Configure it on your machine, then tell me it worked.

## 1. Create a free account

1. Open [https://tidy3d.simulation.cloud/signup](https://tidy3d.simulation.cloud/signup)
2. Sign up with email (or Google / GitHub if offered).
3. Confirm the email if they send one.
4. A free account includes starter **FlexCredits**. That is enough for the 2-D coupler check we want (several short 2-D jobs, not a 3-D inverse-design marathon).

Academic users can also apply for extra credits: [Educational licenses](https://www.flexcompute.com/tidy3d/educational-licenses/).

## 2. Copy the API key

1. Sign in at [https://tidy3d.simulation.cloud](https://tidy3d.simulation.cloud)
2. Open **Account Center** (account icon, left side).
3. Open the **API key** tab:  
   [https://tidy3d.simulation.cloud/account?tab=apikey](https://tidy3d.simulation.cloud/account?tab=apikey)
4. Copy the key. It is a long token. Treat it like a password.

## 3. Configure this machine (pick one)

In PowerShell, from anywhere:

```powershell
tidy3d configure --apikey=PASTE_THE_KEY_HERE
```

Or, if `tidy3d` is not on your PATH:

```powershell
python -m tidy3d.web.cli configure --apikey=PASTE_THE_KEY_HERE
```

Or set a user environment variable (survives new terminals):

```powershell
setx TIDY3D_API_KEY "PASTE_THE_KEY_HERE"
```

Then **close and reopen** the terminal so `setx` is visible.

This repo also reads `TIDY3D_API_KEY` from `F:\Repos\Engineering\.env` via `analysis/_auth_tidy3d.py`. Put the key on that line in `.env` and do not paste it into chat.

## 4. Test without sending the key to me

```powershell
python -c "import tidy3d; tidy3d.web.test()"
```

- Success: no error, often a short “authenticated” message.
- Failure: it will say the key is missing or invalid. Recheck step 2–3.

When that command succeeds, reply **“key is configured”** (still don’t paste the key). I will run the finer 2-D Tidy3D comparison: exact 1550 nm, chirp included in the etch sweep, tighter grid than our 25 nm in-house FDTD.
