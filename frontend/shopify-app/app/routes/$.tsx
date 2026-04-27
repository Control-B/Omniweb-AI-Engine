import { json } from "@remix-run/node";
import type { LoaderFunctionArgs } from "@remix-run/node";

export async function loader({ request }: LoaderFunctionArgs) {
  throw json(
    { message: `No route matches URL "${new URL(request.url).pathname}"` },
    { status: 404 }
  );
}
