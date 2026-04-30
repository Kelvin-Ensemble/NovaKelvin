import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { Button } from './ui/Button';

interface DonationProps {
  onBack: () => void;
  onContinue: (amount: number) => void;
  onSkip: () => void;
  donationAmounts: number[];
  loading?: boolean;
}

export const Donation: React.FC<DonationProps> = ({
  onBack,
  onContinue,
  onSkip,
  donationAmounts,
  loading = false
}) => {
  const [selectedAmount, setSelectedAmount] = useState<number | null>(null);

  const handleDonationClick = (amount: number) => {
    setSelectedAmount(amount);
  };

  const handleAddDonation = () => {
    if (selectedAmount !== null) {
      onContinue(selectedAmount);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">Support Our Orchestra</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p>Would you like to add a donation to support our orchestra? Any donations would be greatly appreciated.</p>

        <div className="flex flex-wrap justify-center gap-4">
          {donationAmounts.map((amount) => (
            <Button
              key={amount}
              onClick={() => handleDonationClick(amount)}
              variant={selectedAmount === amount ? "default" : "outline"}
              className="w-[calc(33.333%-0.667rem)] sm:w-[calc(20%-0.8rem)]"
              disabled={loading}
            >
              £{amount}
            </Button>
          ))}
        </div>

        <div className="flex gap-4 pt-4">
          <Button
            onClick={onBack}
            variant="outline"
            className="flex-1"
            disabled={loading}
          >
            Back
          </Button>
          <Button
            onClick={onSkip}
            variant="outline"
            className="flex-1"
            disabled={loading}
          >
            Skip
          </Button>
          <Button
            onClick={handleAddDonation}
            disabled={selectedAmount === null || loading}
            className="flex-1"
          >
            {loading ? 'Processing...' : 'Add Donation'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};