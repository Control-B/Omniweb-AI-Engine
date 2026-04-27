import { redirect } from "@remix-run/node";

export async function loader() {
  return redirect("/app/pricing");
}

export async function action() {
  return redirect("/app/pricing");
}
