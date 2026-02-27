"use client";

import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Checkbox,
  Badge,
  Text,
  VStack,
} from "@chakra-ui/react";
import type { GameFile } from "@/lib/api/types";

interface GameListProps {
  games: GameFile[];
  selectedGames: number[];
  onSelectionChange: (selected: number[]) => void;
}

export function GameList({
  games,
  selectedGames,
  onSelectionChange,
}: GameListProps) {
  const isSelected = (id: number) => selectedGames.includes(id);

  const toggleGame = (id: number) => {
    if (isSelected(id)) {
      onSelectionChange(selectedGames.filter((gid) => gid !== id));
    } else {
      onSelectionChange([...selectedGames, id]);
    }
  };

  const toggleAll = () => {
    if (selectedGames.length === games.length) {
      onSelectionChange([]);
    } else {
      onSelectionChange(games.map((g) => g.id));
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "green";
      case "downloading":
        return "blue";
      case "pending":
        return "gray";
      case "failed":
        return "red";
      default:
        return "gray";
    }
  };

  if (games.length === 0) {
    return (
      <Box textAlign="center" py={10}>
        <Text color="gray.500">No games found. Try searching for something!</Text>
      </Box>
    );
  }

  return (
    <VStack align="stretch" spacing={4}>
      <Text fontWeight="bold">{games.length} results</Text>
      <Box overflowX="auto">
        <Table variant="simple">
          <Thead>
            <Tr>
              <Th>
                <Checkbox
                  isChecked={selectedGames.length === games.length}
                  isIndeterminate={
                    selectedGames.length > 0 &&
                    selectedGames.length < games.length
                  }
                  onChange={toggleAll}
                />
              </Th>
              <Th>Name</Th>
              <Th>Console</Th>
              <Th>Collection</Th>
              <Th>Size</Th>
              <Th>Status</Th>
            </Tr>
          </Thead>
          <Tbody>
            {games.map((game) => (
              <Tr key={game.id}>
                <Td>
                  <Checkbox
                    isChecked={isSelected(game.id)}
                    onChange={() => toggleGame(game.id)}
                  />
                </Td>
                <Td>
                  <Text fontWeight="medium">{game.name}</Text>
                  {game.region && (
                    <Text fontSize="sm" color="gray.500">
                      {game.region}
                    </Text>
                  )}
                </Td>
                <Td>{game.console || "-"}</Td>
                <Td>
                  <Badge colorScheme="purple">{game.collection}</Badge>
                </Td>
                <Td>{game.formatted_size}</Td>
                <Td>
                  <Badge colorScheme={getStatusColor(game.status)}>
                    {game.status}
                  </Badge>
                  {game.status === "downloading" && (
                    <Text fontSize="sm" color="gray.500">
                      {game.download_progress.toFixed(1)}%
                    </Text>
                  )}
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
    </VStack>
  );
}
