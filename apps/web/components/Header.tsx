import Link from "next/link";

import SignOutButton from "./SignOutButton";

export function Header({ email }: { email?: string | null }) {
  return (
    <header className="flex items-center justify-between border-b border-border/60 px-6 py-4">
      <Link href="/app" className="flex items-baseline gap-2">
        <span className="text-lg font-semibold tracking-tight">Kidroo</span>
        <span className="text-xs text-muted-foreground">agentic YT pipeline</span>
      </Link>
      <div className="flex items-center gap-3 text-sm">
        {email ? (
          <>
            <span className="hidden text-muted-foreground sm:inline">{email}</span>
            <SignOutButton />
          </>
        ) : null}
      </div>
    </header>
  );
}

export default Header;
