import {
    get,
    post,
} from "./api";

export async function getSubscriptionPlans() {

    const response = await get("/subscriptions/plans");

    return response.plans || [];

}

export async function getMySubscription() {

    return get("/subscriptions/me");

}

export async function startMpesaPayment(data) {

    return post(

        "/subscriptions/checkout",

        data,

    );

}

export async function getCheckoutStatus(checkoutRequestId) {
    return get(
        `/subscriptions/checkout-status/${checkoutRequestId}`
    );
}

export async function getSubscriptionStatus(reference) {

    return get(

        `/subscriptions/status/${reference}`

    );

}

export async function cancelSubscription() {

    return post(

        "/subscriptions/cancel"

    );

}
