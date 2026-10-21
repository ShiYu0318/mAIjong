/** English text for the tutor lessons; tiles and answers come from lessons.ts. */

export interface LessonTextEn {
  title: string;
  summary: string;
  sections: { heading: string; body: string[] }[];
  quiz: { question: string; options: string[]; why: string }[];
}

export const LESSONS_EN: Record<string, LessonTextEn> = {
  tiles: {
    title: "Meet the tiles",
    summary: "144 tiles: suit tiles, honor tiles and flowers.",
    sections: [
      { heading: "Suit tiles", body: ["Characters, bamboo and dots each run from 1 to 9, four of each: 108 tiles.", "Characters show a numeral and a red 萬, bamboo shows sticks, dots show circles."] },
      { heading: "Honor tiles", body: ["Winds: East, South, West, North. Dragons: Red, Green, White. Four of each: 28 tiles."] },
      { heading: "Flowers", body: ["Spring, Summer, Autumn, Winter and Plum, Orchid, Chrysanthemum, Bamboo, one of each: 8 tiles. Flowers never stay in your hand; show one as soon as you draw it and draw a replacement."] },
    ],
    quiz: [
      { question: "How many tiles are in a Taiwanese 16-tile set?", options: ["136", "144", "152"], why: "108 suit tiles + 28 honors + 8 flowers = 144." },
      { question: "Which of these is a dragon?", options: ["North", "Green", "Spring"], why: "The dragons are Red, Green and White; North is a wind and Spring is a flower." },
    ],
  },
  sets: {
    title: "Chows, pungs and the pair",
    summary: "A winning hand is sets plus one pair.",
    sections: [
      { heading: "Chow", body: ["Three in a row in one suit, such as 3-4-5 characters. Honors can't form chows."] },
      { heading: "Pung and kong", body: ["Three identical tiles are a pung; four identical tiles can be declared as a kong, which counts as one set."] },
      { heading: "The pair", body: ["Two identical tiles. A winning hand needs exactly one pair."] },
    ],
    quiz: [
      { question: "Can East, South, West make a chow?", options: ["Yes", "No"], why: "Only characters, bamboo and dots form chows." },
      { question: "After declaring four identical tiles as a kong, how many sets is that?", options: ["One", "Two"], why: "A kong is one set; you draw a replacement for the extra tile from the back of the wall." },
    ],
  },
  winning: {
    title: "How a hand wins",
    summary: "In 16-tile mahjong you win with 5 sets and 1 pair: 17 tiles.",
    sections: [
      { heading: "Hand size", body: ["Everyone holds 16 tiles; the dealer takes 1 extra and discards first.", "On your turn you draw one and discard one, keeping 16 in hand."] },
      { heading: "Winning", body: ["Make 5 sets (chows, pungs or kongs) plus 1 pair and you win.", "Winning on your own draw is a self-draw; winning on someone's discard means that player dealt in."] },
      { heading: "Drawn hands", body: ["The last 16 tiles of the wall can't be drawn (one more is kept back for every kong). If nobody wins before then, the hand is drawn and the dealer stays on."] },
    ],
    quiz: [
      { question: "How many sets does a winning hand have?", options: ["4", "5", "6"], why: "A 16-tile winning hand is 5 sets plus 1 pair." },
      { question: "Who deals after a drawn hand?", options: ["The next player", "The same dealer"], why: "Under Taiwanese 16-tile rules the dealer stays on after a draw." },
    ],
  },
  flowers: {
    title: "Flowers",
    summary: "Only the flowers that match your seat score tai.",
    sections: [
      { heading: "Replacing flowers", body: ["Show a flower as soon as you draw it and take a replacement from the back of the wall. At the start, players replace flowers in turn starting with the dealer."] },
      { heading: "Your own flowers", body: ["East owns Spring and Plum; South Summer and Orchid; West Autumn and Chrysanthemum; North Winter and Bamboo. Each of your own flowers is 1 tai.", "All four of one set (the seasons or the plants) is a flower kong, scoring 2 tai for that set instead."] },
      { heading: "Eight immortals and seven robs one", body: ["Collecting all 8 flowers wins outright for 8 tai, and all three others pay.", "If you hold 7 flowers and someone else draws the 8th, you can take it and win; that player pays 8 tai."] },
    ],
    quiz: [
      { question: "South holds Orchid. How many tai is that?", options: ["0 tai", "1 tai", "2 tai"], why: "South's own flowers are Summer and Orchid, 1 tai each." },
      { question: "Who pays for eight immortals?", options: ["Only the dealer", "All three others"], why: "It counts as a self-draw, so all three pay 8 tai." },
    ],
  },
  calls: {
    title: "Chow, pung and kong calls",
    summary: "Use other players' discards to make sets, with priorities and limits.",
    sections: [
      { heading: "Chow and pung", body: ["Chow: only the discard of the player before you, to make a run. Pung: anyone's discard, if you hold a pair of it.", "A win on the same tile beats everything; pung and kong beat chow."] },
      { heading: "Three kinds of kong", body: ["Exposed kong: you hold three and call the fourth from someone's discard (not from the player before you).", "Concealed kong: you draw all four yourself. Added kong: you already called a pung and add the fourth when you draw it.", "Others can rob an added kong to win."] },
      { heading: "Limits after a call", body: ["After a chow or pung you must discard right away; you can't kong next.", "You can't discard the tile you just called, and after a chow you can't discard the other end of the run (calling 3 with 4-5 means no 3 or 6).", "With 3 or fewer tiles left in the wall you can't chow, pung or call an exposed kong."] },
    ],
    quiz: [
      { question: "Can you chow the discard of the player across from you?", options: ["Yes", "No"], why: "You can only chow the discard of the player before you." },
      { question: "You chowed 3 bamboo with 4 and 5. What can't you discard next?", options: ["3 and 6 bamboo", "Only 3 bamboo", "No limit"], why: "You can't discard the same tile or the other end of the run." },
      { question: "Two players want to win on the same discard. What happens?", options: ["Both win", "The one closest after the discarder wins"], why: "Taiwanese 16-tile uses head bump: only one player wins." },
    ],
  },
  tai: {
    title: "Counting tai",
    summary: "Payment = base + tai × per tai.",
    sections: [
      { heading: "The formula", body: ["At 100 base / 50 per tai, a 4-tai win off a discard costs the discarder 100 + 4 × 50 = 300.", "On a self-draw all three others pay; on a discard win only the discarder pays."] },
      { heading: "Common tai", body: ["Concealed 1, self-draw 1, concealed self-draw 3, declared ready 1, round or seat wind pung 1 each, dragon pung 1.", "All chows 2, three concealed pungs 2, all pungs 4, half flush 4, full flush 8, big three dragons 8, big four winds 16.", "You can win with no tai at all (a chicken hand) and collect just the base."] },
      { heading: "Dealer tai", body: ["When the dealer wins or deals in, add 1 tai; for N consecutive deals add another 2N (staying on once is 2 tai).", "Dealer tai only counts between the dealer and the other player involved."] },
    ],
    quiz: [
      { question: "How many tai is a concealed self-draw?", options: ["2 tai", "3 tai"], why: "Concealed plus self-draw together score 3 tai." },
      { question: "A non-dealer deals in to another non-dealer. Does the dealer pay?", options: ["Yes", "No"], why: "On a discard win only the discarder pays." },
    ],
  },
  discard: {
    title: "Discard basics",
    summary: "Get closer to ready and keep more useful tiles.",
    sections: [
      { heading: "Steps from ready", body: ["Shanten counts how many steps you are from ready. 0 means ready; 1 means one away.", "First rule of discarding: don't move further from ready."] },
      { heading: "Useful tiles", body: ["Tiles that bring you closer to ready are useful tiles. When two discards leave you equally close, keep the one with more useful tiles.", "An open-ended pair (4-5, waiting on 3 or 6) beats a closed wait (4-6, waiting on 5) or an edge wait (1-2, waiting on 3)."] },
      { heading: "Declaring ready", body: ["You can declare when you're ready: a win scores 1 more tai, but you can't change your hand afterwards.", "Declaring on your first discard (ready from the deal) scores 4 tai."] },
    ],
    quiz: [
      { question: "What does 0 shanten mean?", options: ["Already won", "Ready"], why: "0 shanten is ready: one more tile wins." },
      { question: "Which pair of tiles has the most useful draws?", options: ["4 5", "4 6", "1 2"], why: "An open-ended pair waits on two kinds of tile." },
    ],
  },
  defense: {
    title: "Defence basics",
    summary: "Watch who's ready and give up your hand when you must.",
    sections: [
      { heading: "Opponents who declared", body: ["A player who declared ready can't change their hand. Any tile discarded after the declaration that they didn't win on isn't one they need: it's safe."] },
      { heading: "When to fold", body: ["When you're far from ready and an opponent is ready, discard safe tiles first to avoid dealing in.", "Late in the hand (under 24 tiles left) be extra careful with tiles nobody has discarded yet."] },
      { heading: "Passing on a win", body: ["Choosing not to win when you could is passing. After passing you can't win, not even by self-draw, until your next discard."] },
    ],
    quiz: [
      { question: "An opponent declared ready, then someone discarded 5 dots and they didn't win. To them, 5 dots is…", options: ["Safe", "Dangerous"], why: "They can't change their hand after declaring, so 5 dots isn't a tile they need." },
      { question: "After passing on a win, can you win on your next draw?", options: ["Yes", "No"], why: "While passing you can't even self-draw; it ends once you discard a tile." },
    ],
  },
};
