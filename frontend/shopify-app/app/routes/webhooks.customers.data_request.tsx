import { authenticate } from "../shopify.server";

export async function action({ request }: { request: Request }) {
  await authenticate.webhook(request);
  // TODO: enqueue GDPR customer data export for conversations tied to this customer.
  return new Response();
}
