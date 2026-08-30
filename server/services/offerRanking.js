import { estimateEmi } from "./indiaProfile.js";

export const rankOffers = (offers, input, profile) => {
  const lowestRate = Math.min(...offers.map((offer) => offer.interestRate));

  return offers
    .map((offer) => {
      const interestScore = lowestRate / offer.interestRate;
      const amountMatch = Math.min(1, input.amount / offer.maxAmount);
      const profileFit = offer.profileFit ?? 0.5;
      const score =
        0.3 * offer.approvalProbability +
        0.2 * interestScore +
        0.15 * amountMatch +
        0.2 * profileFit +
        0.1 * offer.successRate +
        0.05 * offer.journeyScore;

      return {
        ...offer,
        score: Number(score.toFixed(3)),
        monthlyPayment: Math.round(
          estimateEmi(input.amount, offer.interestRate, input.tenureMonths),
        ),
        routingReason:
          offer.rank === 1
            ? `Best fit for ${profile.label} segment`
            : undefined,
      };
    })
    .sort((a, b) => b.score - a.score)
    .map((offer, index) => ({
      ...offer,
      rank: index + 1,
      routingReason:
        index === 0
          ? `Best fit for ${profile.label} applicants in tier-${input.cityTier} cities`
          : `Alternative ${profile.label.toLowerCase()} offer`,
    }));
};
